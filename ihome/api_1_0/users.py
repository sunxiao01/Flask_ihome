# coding=utf-8
from flask import request, jsonify, current_app, session, g
from ihome.response_code import RET
from ihome.models import User
from ihome.utils.commons import login_required
import re
from . import api
from ihome import db, constants
from ihome.utils.image_storage import storage


@api.route('sessions', methods=['POST'])
def login():
    """
    处理用户登录
    1. 获取参数：用户名、密码
    2. 请求方式POST
    3. 校验参数是否都存在
    4. 校验手机号是否符合正则规则
    5. 连接mysql数据库，查询手机号是否存在
    6. 如果用户存在，查询密码，校验密码是否一致
    7. 缓存用户信息到redis
    8. 登录成功
    :return:
    """
    # 1. 获取参数
    user_data = request.get_json()
    if not user_data:
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
    # 获取详细参数mobile和password
    mobile = user_data.get('mobile')
    password = user_data.get('password')

    # 2. 判断参数是否为空
    if not all([mobile, password]):
        return jsonify(errno=RET.DATAERR, errmsg='参数不完整')

    # 3. 正则校验手机号
    if not re.match(r'^1[3-9]\d{9}$', mobile):
        return jsonify(errno=RET.DATAERR, errmsg='您输入的手机号不合法')

    # 4. 查询数据库
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询数据库异常')
    # 判断手机号和密码是否正确
    if user is None or not user.check_password(password):
        return jsonify(errno=RET.DATAERR, errmsg='您输入的用户名或密码错误')

    # 5.更新缓存中的信息
    session['user_id'] = user.id
    session['name'] = user.name
    session['mobile'] = user.mobile

    return jsonify(errno=RET.OK, errmsg='OK')


@api.route('user', methods=['GET'])
@login_required
def get_user_profile():
    """
    查询用户信息
    1. 无参数
    2. 根据User_id获取用户的name和avater_name信息
    2. 将查询到的avatar_url拼接为绝对路径返回给浏览器
    3. 将用户名name返回给浏览器
    """
    # 1. 查询当前登录的用户的用户信息
    user_id = g.user_id
    try:
        user = User.query.filter_by(id=user_id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询用户信息失败')

    if not user:
        return jsonify(errno=RET.NODATA, errmsg='无效操作信息')

    return jsonify(errno=RET.OK, errmsg='OK', data=user.to_dict())


@api.route('user/name', methods=['PUT'])
@login_required
def set_username():
    """
    设置用户名
    1. 获取参数：用户名
    2. 校验获取的参数：name 是否为空
    3. 通过use_id查询用户是否正常
    4. 将name保存到数据库
    5. 返回结果
    """
    # 1. 获取用户参数
    user_data = request.get_json()
    user_id = g.user_id
    if user_data is None:
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误')
    # 获取用户名
    name = user_data.get('name')
    # 2.校验用户名
    if name is None:
        return jsonify(errno=RET.DATAERR, ermsg='参数缺失')

    # 3. 从数据库中查询该用户
    try:
        user = User.query.filter_by(id=user_id).update({'name': name})
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='更新用户信息失败')

    # 4.保存更新的后的用户名到redis
    session['name']=name
    return jsonify(errno=RET.OK, errmsg='OK')


@api.route('user/avatar', methods=['POST'])
@login_required
def set_user_avatar():
    """
    设置用户头像
    1. 获取用户头像参数
    2. 验证用户头像数据是否为空
    3. 头像上传到七牛云服务
    4. 将返回的图图片名称保存到数据库
    5. 返回保存结果
    """
    # 1.获取用户头像信息，并验证
    avatar = request.files.get('avatar')
    user_id = g.user_id
    if not avatar:
        return jsonify(errno=RET.PARAMERR, errmsg='未上传头像')
    avatar_data = avatar.read()
    # 2. 上传头像信息到七牛云
    try:
        # 保存成功后返回图片再七牛云上名称
        result = storage(avatar_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg='上传图片到七牛云失败')
    # 3.保存用户名称到数据库
    try:
        User.query.filter_by(id=user_id).update({'avatar_url':result})
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='保存用户头像信息失败')
    # 4. 拼接图片绝对地址信息，返回给浏览器
    image_url = constants.QINIU_DOMIN_PREFIX + result
    print image_url
    # 5. 向浏览器返回成功的信息
    return jsonify(errno=RET.OK, errmsg='OK', data={'avatar_url': image_url})


@api.route('user/auth', methods=['POST'])
@login_required
def set_user_auth():
    """
    设置用户实名认证信息
    1. 获取用户参数
    2. 获取详细信息：身份证和姓名信息
    3. 验证用户信息是否存在
    4. 保存用户实名认证信息到数据库
    5. 返回结果
    """
    # 1. 获取参数
    user_data = request.get_json()
    user_id = g.user_id
    if not user_data:
        return jsonify(errno=RET.PARAMERR, errmsg='参数错误，不允许为空')
    # 2. 获取详细参数
    id_card = user_data.get('id_card')
    real_name = user_data.get('real_name')

    # 3. 验证数据不为空
    if not all([id_card, real_name]):
        return jsonify(errno=RET.DATAERR, errmsg='参数不完整')

    # 4. 查询数据库，并将实名认证信息更新到数据库
    try:
        user = User.query.filter_by(id=user_id, id_card=None, real_name=None).update({'real_name':real_name, 'id_card': id_card})
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='保存实名认证信息错误')
    # if not user:
    #     return jsonify(errno=RET.DATAEXIST, errmsg='该用户已经实名认证过')

    return jsonify(errno=RET.OK, errmsg='OK')


@api.route('user/auth', methods=['GET'])
@login_required
def get_user_auth():
    """
    查询用户的实名认证信息
    1. 无参数，获取用户的user_id
    2. 根据用户的user_id查询用户的real_name 和 id_card
    3. 返回查询结果
    :return:
    """
    # 1. 获取用户的user_id
    user_id = g.user_id
    # 2. 根据user_id查询数据库
    try:
        user = User.query.filter_by(id=user_id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询用户信息异常')

    # 3. 判断查询结果
    if not user:
        return jsonify(errno=RET.DATAERR, errmsg='无效操作')

    # 4. 返回查询结果
    return jsonify(errno=RET.OK, errmsg='OK', data=user.auth_to_dict())


@api.route('session', methods=['DELETE'])
@login_required
def logout():
    """
    退出登录
    :return:
    """
    session.clear()
    return jsonify(errno=RET.OK, errmsg='OK')