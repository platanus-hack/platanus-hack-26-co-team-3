function handler(event) {
    var request = event.request;
    var uri = request.uri;

    if (uri === '/api' || uri.indexOf('/api/') === 0) {
        request.uri = uri.replace(/^\/api/, '') || '/';
    }

    return request;
}
