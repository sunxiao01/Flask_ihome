# coding=utf-8

from . import api
from ihome.utils.captcha.captcha import captcha
from ihome import redis_store, constants, db
from flask import current_app, jsonify, make_response, request, session
from ihome.response_code import RET
from ihome.models import User
import re, random
from ihome.utils import sms


@api.route('imagecode/<image_code_id>')
def generate_image_code(image_code_id):
    """
        生成图片验证码:
        1/调用captcha扩展包,生成图片验证码,name,text,image
        2/保存图片验证码的内容,使用redis数据库
        3/返回前端图片
        4/需要设置响应的类型
        :param image_code_id:
        :return:
        """
    # 调用扩展生成图片验证码
    name, text, image = captcha.generate_captcha()
    # with open('1.jpg', 'a') as obj:
    #     obj.write(image)

    try:
        # 保存图片验证码到redis数据库，保存格式为：imagecode_image_code_id, 设置有效期
        redis_store.setex('imagecode_'+image_code_id, constants.IMAGE_CODE_REDIS_EXPIRES, text)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errcode=RET.DBERR, errmsg='保存图片验证码失败')
    else:
        response = make_response(image)
        response.headers['Content-Type'] = 'image/jpg'
        # 返回结果
        return response

@api.route('smscode/<mobile>')
def send_sms_code(mobile):
    """
    发送方式：GET
    1. 获取参数：手机号， 用户输入的验证码， image_code_id
    2. 校验参数存在
    3. 通过正则校验手机号是否为合法手机号
    4. 查询redis数据库获取图片验证码，校验验证码一致
    5. 删除图片验证码，因为验证码只能校验一次
    6. 查询用户手机号是否已注册过
    7. 生成验证码，
    8. 调用云通讯接口发送信息
    :return:
    """
    # 获取参数image_code, image_code_id
    image_code = request.args.get('text')
    image_code_id = request.args.get('id')
    # 校验参数完整
    if not all([mobile, image_code, image_code_id]):
        return jsonify(errcode=RET.PARAMERR, errmsg='参数输入不完整')
    # 通过正则校验手机号合法
    if not re.match(r'^1[3-9]\d{9}$', mobile):
        return jsonify(errcode=RET.PARAMERR, errmsg='手机号不合法')

    # 查询redis数据库, 获取真实的imagecode
    try:
        real_image_code = redis_store.get('imagecode_'+image_code_id)
        print real_image_code
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errcode=RET.DBERR, errmsg='查询图片验证码异常')
    # 判断是否有数据，若无数据则表示已过期
    if not real_image_code:
        return jsonify(errcode=RET.DATAERR, errmsg='图片验证码已过期')

    # 清除redis数据库
    try:
        redis_store.delete('imagecode_'+image_code_id)
    except Exception as e:
        current_app.logger.error(e)
    # 验证用户输入的验证码与真实验证码是否一致
    if image_code.lower() != real_image_code.lower():
        return jsonify(errcode=RET.DATAERR, errmsg='您输入的验证码错误')

    # 查询数据库，验证用户手机号是否已经注册过
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询数据库错误')

    if user is not None:
        return jsonify(errno=RET.DATAERR, errmsg='该手机号已经注册过')

    # 当手机号和图片验证码验证通过后，开始生成短信验证码，然后发送短信验证码
    # 1.随机生成验证码
    sms_code = '%06d' % random.randint(0, 999999)
    # 2. 保存验证码到数据库
    try:
        redis_store.setex('smscode_'+mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
    except Exception:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='存储短信验证码到数据库异常')

    # 3, 保存成功后，调用云通讯发送短信验证码
    try:
        # 实例化云通讯对象
        ccp = sms.CCP()
        result = ccp.send_template_sms(mobile, [sms_code, constants.SMS_CODE_REDIS_EXPIRES/60],1)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg='发送短信验证码异常')
    if result == 0:
        return jsonify(errno=RET.OK, errmsg='发送成功')
    else:
        return jsonify(errno=RET.THIRDERR, errmsg='发送失败')


@api.route('users', methods=['POST'])
def register():
    """
    用户注册模块
    1. 获取用户参数：POST请求：手机号、短信验证码、密码
    2. 校验用户参数：是否均不为空
    3. 通过正则校验手机号是否合法
    4. 校验验证码是否正确
    5. 校验手机号是否已经注册过
    6. 删除比较之后的验证码
    7. 构造模型类，存储用户数据
    8. 缓存用户信息
    9. 返回结果
    :return:
    """
    # 1.获取用户参数:
    user_data = request.get_json()
    if not user_data:
        return jsonify(errno=RET.PARAMERR, errmsg='获取参数错误')
    # 获取详细参数：手机号、短信验证码、 密码
    mobile = user_data.get('mobile')
    sms_code = user_data.get('sms_code')
    password = user_data.get('password')

    # 2. 校验三个参数均存在
    if not all([mobile, sms_code, password]):
        return jsonify(errno=RET.PARAMERR, errmsg='参数不完整')

    # 3. 校验手机号是否合法
    if not re.match(r'^1[3-9]\d{9}$', mobile):
        return jsonify(errcode=RET.PARAMERR, errmsg='手机号不合法')

    # 4. 查询数据库，确认该手机号是否已经注册过
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询用户信息错误')
    # 如果查询的结果不为空，说明该手机号已经被注册过
    if user is not None:
        return jsonify(errno=RET.DATAEXIST, errmsg='该手机号已经注册过')

    # 5. 从redis数据库中查询真实的短信验证码，与用户输入的验证码进行比较
    try:
        real_sms_code = redis_store.get('smscode_'+mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询数据库异常')
    # 如果查询结果为空，说明验证码已过期
    if not real_sms_code:
        return jsonify(errno=RET.PARAMERR, errmsg='验证码已过期')
    # 如果验证不为空，则进行比较
    if real_sms_code != str(sms_code):
        return jsonify(errno=RET.DATAERR, errmsg='验证码错误')
    # 6. 如果验证码已经校验通过后，从redis数据库中删除
    try:
        redis_store.delete('smscode_'+mobile)
    except Exception as e:
        current_app.logger.error(e)

    # 7. 当参数校验无问题之后，保存用户数据到数据库,
    # 首先构造模型类对象，要对密码进行加密
    new_user = User(mobile=mobile, name=mobile)
    new_user.password=password
    try:
        db.session.add(new_user)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='保存数据失败')

    # 8. 缓存用户信息到redis中
    session['mobile']=mobile
    session['use_id']=new_user.id
    session['name']=mobile
    return jsonify(errno=RET.OK, errmsg='OK', data=new_user.to_dict())




















