package gateway

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"

	"roxy-gateway/internal/policy"
)

type PlannedCall struct {
	Method    string
	URL       string
	Body      json.RawMessage
	SessionID string
}

func normalizePlan(baseURL string, raw []byte) (PlannedCall, error) {
	var parsed struct {
		Method    string          `json:"method"`
		URL       string          `json:"url"`
		Path      string          `json:"path"`
		Body      json.RawMessage `json:"body"`
		SessionID string          `json:"sessionId"`
	}
	text := extractJSONObject(string(raw))
	if err := json.Unmarshal([]byte(text), &parsed); err != nil {
		return PlannedCall{}, fmt.Errorf("%w: %v", policy.ErrPlan, err)
	}
	method := strings.ToUpper(strings.TrimSpace(parsed.Method))
	if method == "" {
		method = http.MethodPost
	}
	switch method {
	case http.MethodGet, http.MethodPost, http.MethodPut, http.MethodPatch, http.MethodDelete:
	default:
		return PlannedCall{}, fmt.Errorf("%w: unsupported method %q", policy.ErrPlan, method)
	}

	target := strings.TrimSpace(parsed.URL)
	if target == "" {
		target = strings.TrimSpace(parsed.Path)
	}
	resolved, err := resolveAgainstBase(baseURL, target)
	if err != nil {
		return PlannedCall{}, err
	}

	body := parsed.Body
	if method == http.MethodGet {
		body = nil
	}
	return PlannedCall{Method: method, URL: resolved, Body: body, SessionID: strings.TrimSpace(parsed.SessionID)}, nil
}

func resolveAgainstBase(baseURL, planned string) (string, error) {
	base, err := url.Parse(strings.TrimSpace(baseURL))
	if err != nil || base.Scheme == "" || base.Host == "" {
		return "", fmt.Errorf("%w: invalid mcp base url", policy.ErrPlan)
	}
	if strings.TrimSpace(planned) == "" {
		return strings.TrimRight(base.String(), "/"), nil
	}
	ref, err := url.Parse(planned)
	if err != nil {
		return "", fmt.Errorf("%w: invalid planned url", policy.ErrPlan)
	}
	if ref.IsAbs() {
		if !strings.EqualFold(ref.Scheme, base.Scheme) || !strings.EqualFold(ref.Host, base.Host) {
			return "", fmt.Errorf("%w: planned url host mismatch", policy.ErrPlan)
		}
		return ref.String(), nil
	}
	base.Path = strings.TrimRight(base.Path, "/")
	if strings.HasPrefix(ref.Path, "/") {
		base.Path += ref.Path
	} else {
		base.Path += "/" + ref.Path
	}
	base.RawQuery = ref.RawQuery
	base.Fragment = ref.Fragment
	return base.String(), nil
}

func extractJSONObject(text string) string {
	start := strings.Index(text, "{")
	end := strings.LastIndex(text, "}")
	if start >= 0 && end > start {
		return text[start : end+1]
	}
	return strings.TrimSpace(text)
}

func planHasBody(body json.RawMessage) bool {
	trim := bytes.TrimSpace(body)
	if len(trim) == 0 || bytes.Equal(trim, []byte("null")) {
		return false
	}
	return true
}
