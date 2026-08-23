package gateway

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"roxy-gateway/internal/mcp"
	"roxy-gateway/internal/policy"
)

const defaultAtlasTokenURL = "https://cloud.mongodb.com/api/oauth/token"

type oauthCreds struct {
	ClientID     string `json:"clientId"`
	ClientSecret string `json:"clientSecret"`
	TokenURL     string `json:"tokenURL"`
}

func parseOAuthCreds(raw string) (oauthCreds, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return oauthCreds{}, fmt.Errorf("%w: oauth2 credentials empty", policy.ErrUpstream)
	}
	if strings.HasPrefix(raw, "{") {
		var c oauthCreds
		if err := json.Unmarshal([]byte(raw), &c); err != nil {
			return oauthCreds{}, fmt.Errorf("%w: oauth2 credentials json: %v", policy.ErrUpstream, err)
		}
		if c.ClientID == "" || c.ClientSecret == "" {
			return oauthCreds{}, fmt.Errorf("%w: oauth2 credentials missing clientId/clientSecret", policy.ErrUpstream)
		}
		return c, nil
	}
	id, secret, ok := strings.Cut(raw, ":")
	if !ok || id == "" || secret == "" {
		return oauthCreds{}, fmt.Errorf("%w: oauth2 credentials must be clientId:clientSecret", policy.ErrUpstream)
	}
	return oauthCreds{ClientID: id, ClientSecret: secret}, nil
}

func (c *MCPClient) resolveBearer(ctx context.Context, auth mcp.Authorization) (string, error) {
	if strings.EqualFold(auth.Type, "apikey") {
		return "", nil
	}
	if !strings.EqualFold(auth.Type, "oauth2") {
		return auth.Credentials, nil
	}
	creds, err := parseOAuthCreds(auth.Credentials)
	if err != nil {
		return "", err
	}
	tokenURL := creds.TokenURL
	if tokenURL == "" {
		tokenURL = defaultAtlasTokenURL
	}
	cacheKey := tokenURL + "\x00" + creds.ClientID + "\x00" + creds.ClientSecret
	c.mu.Lock()
	if c.cachedTok != "" && c.cachedKey == cacheKey && time.Now().Before(c.cachedExp) {
		tok := c.cachedTok
		c.mu.Unlock()
		return tok, nil
	}
	c.mu.Unlock()

	tok, exp, err := fetchClientCredentialsToken(ctx, c.httpClient, tokenURL, creds.ClientID, creds.ClientSecret)
	if err != nil {
		return "", err
	}
	c.mu.Lock()
	c.cachedKey = cacheKey
	c.cachedTok = tok
	c.cachedExp = exp.Add(-60 * time.Second)
	c.mu.Unlock()
	return tok, nil
}

type tokenResponse struct {
	AccessToken string `json:"access_token"`
	ExpiresIn   int    `json:"expires_in"`
}

func fetchClientCredentialsToken(ctx context.Context, hc *http.Client, tokenURL, clientID, clientSecret string) (string, time.Time, error) {
	form := url.Values{}
	form.Set("grant_type", "client_credentials")
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, tokenURL, strings.NewReader(form.Encode()))
	if err != nil {
		return "", time.Time{}, fmt.Errorf("%w: %v", policy.ErrUpstream, err)
	}
	req.SetBasicAuth(clientID, clientSecret)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Accept", "application/json")
	res, err := hc.Do(req)
	if err != nil {
		return "", time.Time{}, fmt.Errorf("%w: oauth token: %v", policy.ErrUpstream, err)
	}
	defer res.Body.Close()
	raw, err := io.ReadAll(res.Body)
	if err != nil {
		return "", time.Time{}, fmt.Errorf("%w: oauth token: %v", policy.ErrUpstream, err)
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return "", time.Time{}, fmt.Errorf("%w: oauth token status %d", policy.ErrUpstream, res.StatusCode)
	}
	var parsed tokenResponse
	if err := json.Unmarshal(raw, &parsed); err != nil || parsed.AccessToken == "" {
		return "", time.Time{}, fmt.Errorf("%w: oauth token missing access_token", policy.ErrUpstream)
	}
	ttl := parsed.ExpiresIn
	if ttl <= 0 {
		ttl = 3600
	}
	return parsed.AccessToken, time.Now().Add(time.Duration(ttl) * time.Second), nil
}
