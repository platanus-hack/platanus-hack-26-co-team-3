function handler(event) {
    var request = event.request;
    var uri = request.uri;

    if (uri === '/demo-api' || uri.indexOf('/demo-api/') === 0) {
        request.uri = uri.replace(/^\/demo-api/, '') || '/';
    }

    return request;
}
