(function (global) {
    function getApiBaseUrl() {
        if (global && global.__SIA_API_BASE_URL) return global.__SIA_API_BASE_URL;
        if (global && global.location && global.location.origin) return global.location.origin;
        return 'http://localhost:8000';
    }

    global.SIAUtils = Object.assign({}, global.SIAUtils, {
        getApiBaseUrl
    });
})(window);

