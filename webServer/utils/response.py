from flask import jsonify

class ResponseCode:
    SUCCESS = 0
    FAIL = 1
    NOT_FOUND = 404
    SERVER_ERROR = 500


def success(data=None, msg="success"):
    """成功响应"""
    return jsonify({
        "code": ResponseCode.SUCCESS,
        "msg": msg,
        "data": data
    }), 200


def fail(msg="fail", code=ResponseCode.FAIL, data=None, http_status=400):
    """失败响应"""
    return jsonify({
        "code": code,
        "msg": msg,
        "data": data
    }), http_status
