package dashboard

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"roxy-gateway/internal/mcp"
)

type Notification struct {
	Status       string    `json:"status"`
	MCPName      string    `json:"mcpName"`
	MCPID        string    `json:"mcpId"`
	AccessedBy   string    `json:"accessedBy"`
	Action       string    `json:"action"`
	ViolatedRule *mcp.Rule `json:"violatedRule,omitempty"`
	Description  string    `json:"description"`
	Time         time.Time `json:"time"`
}

type Notifier interface {
	Notify(ctx context.Context, n Notification) error
}

type Client struct {
	url        string
	httpClient *http.Client
}

func NewClient(url string) *Client {
	return &Client{
		url:        url,
		httpClient: &http.Client{Timeout: 2 * time.Second},
	}
}

func (c *Client) Notify(ctx context.Context, n Notification) error {
	if c.url == "" {
		return nil
	}
	body, err := json.Marshal(n)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.url, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	res, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer res.Body.Close()
	if res.StatusCode >= 300 {
		return fmt.Errorf("dashboard status %d", res.StatusCode)
	}
	return nil
}
