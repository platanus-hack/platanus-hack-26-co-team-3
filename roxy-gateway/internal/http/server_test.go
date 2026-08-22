package httpapi_test

import (
	"net/http"
	"net/http/httptest"
	"testing"

	httpapi "roxy-gateway/internal/http"

	"github.com/stretchr/testify/require"
)

func TestHealth(t *testing.T) {
	t.Parallel()
	r := httpapi.NewRouter(stubService{})
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	require.Equal(t, http.StatusOK, w.Code)
	require.Contains(t, w.Body.String(), `"service":"roxy"`)
}
