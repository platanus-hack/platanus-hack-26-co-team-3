function handler(event) {
    var request = event.request;
    var uri = request.uri;

    if (uri === '/gateway' || uri.indexOf('/gateway/') === 0) {
        request.uri = uri.replace(/^\/gateway/, '') || '/';
    }

    return request;
}
