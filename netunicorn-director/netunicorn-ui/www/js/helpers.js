function check_authentication() {
    var token = window.ls.get('netunicorn_access_token');
    if (token == null) {
        window.location.href = 'login.html';
    }
}

function logout() {
    window.ls.remove('netunicorn_access_token');
    window.location.href = 'login.html';
}