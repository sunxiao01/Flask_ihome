# coding=utf-8

from . import api
from ihome import redis_store, constants, db
from flask import current_app, jsonify, request, g
from ihome.models import Area, Facility, House, HouseImage
from ihome.response_code import RET
import json
from ihome.utils.commons import login_required
from ihome.utils.image_storage import storage


@api.route('areas', methods=['GET'])
def get_areas():
    """
    获取城区信息
    1. 无参数
    2. 不需要验证用户登录
    3. 尝试从redis数据库中获取城区信息，
    4. 校验数据，若有数据则直接返回给浏览器，若redis中无缓存数据，则查询数据库
    5.
    6. 询Area的信息，并返回给浏览器
    :return:
    """
    # 查询redis中的缓存信息
    try:
        areas = redis_store.get('areas')
    except Exception as e:
        current_app.logger.error(e)
        areas = None
    # 如果查询有数据，则直接返回结果，
    if areas:
        current_app.logger.info('get areas info from redis')
        print areas
        return '{"errno":0,"errmsg":"OK","data":%s}' % areas
    # 如果查询无数据， 则进入mysql中查询
    try:
        areas = Area.query.all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库查询异常')
    # 校验areas 是否为空，如果为空
    if not areas:
        return jsonify(errno=RET.NODATA, errmsg='没有城区信息')

    # 如果数据不为空，则遍历一下
    arealist = []
    for area in areas:
        arealist.append(area.to_dict())
    # 将数据转环卫json
    area_json = json.dumps(arealist)
    print area_json

    # 将数据保存到redis缓存中
    try:
        redis_store.setex('areas', constants.AREA_INFO_REDIS_EXPIRES, area_json)
    except Exception as e:
        current_app.logger.error(e)

    # 将城区信息返回给浏览器
    resp = '{"errno":0, "errmsg":"OK", "data":%s}' % area_json
    return resp


@api.route('houses', methods=['POST'])
@login_required
def set_house_info():
    """
    设置房屋信息
    1. 获取必选参数
    2. 校验必选参数
    3. 获取方位配套设施参数
    4. 校验配套设施是否为有效数据，保留有效数据，去掉无效数据
    5. 构建模型对象，保存到数据库
    6. 保存房屋设施
    7. 保存成功后，返回数据

    :return:
    """
    # 1. 获取房屋信息参数
    house_data = request.get_json()
    user_id = g.user_id
    title = house_data.get('title')
    price = house_data.get('price')
    area_id = house_data.get('area_id')
    address = house_data.get('address')
    room_count = house_data.get('room_count')
    acreage = house_data.get('acreage')
    unit = house_data.get('unit')
    capacity = house_data.get('capacity')
    beds = house_data.get('beds')
    deposit = house_data.get('deposit')
    min_days = house_data.get('min_days')
    max_days = house_data.get('max_days')
    # 2. 校验所有参数不为空
    if not all([title, price, area_id, address, room_count, acreage, unit, capacity, beds, deposit, min_days, max_days]):
        return jsonify(errno=RET.PARAMERR, errmsg='参数缺失')

    # 3. 处理price和depoist的金钱信息，将“元”转化为“分”
    try:
        price = int(float(price)*100)
        deposit = int(float(deposit)*100)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR, errmsg='价格或押金数据错误')

    # 6. 构造模型对象
    house = House()
    house.user_id = user_id
    house.area_id = area_id  # 归属地的区域编号
    house.title = title  # 标题
    house.price = price  # 单价，单位：分
    house.address = address  # 地址
    house.room_count = room_count  # 房间数目
    house.acreage = acreage  # 房屋面积
    house.unit = unit  # 房屋单元， 如几室几厅
    house.capacity = capacity  # 房屋容纳的人数
    house.beds = beds  # 房屋床铺的配置
    house.deposit = deposit  # 房屋押金
    house.min_days = min_days  # 最少入住天数
    house.max_days = max_days  # 最多入住天数，0表示不限制

    # 4. 获取房屋配额设施
    facility = house_data.get('facility')
    print facility

    # 5. 验证房屋数据是否有效，去掉无效数据
    if facility:
        try:
            facilities = Facility.query.filter(Facility.id.in_(facility)).all()
            house.facilities = facilities
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DATAERR, errmsg='获取用户设施失败')

    # 7. 向数据库中保存模型对象
    try:
        db.session.add(house)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='保存数据异常')

    return jsonify(errno=RET.OK, errmsg='OK', data={'house_id': house.id})


@api.route('houses/<int:house_id>/images', methods=['POST'])
def set_house_images(house_id):
    """
    获取参数
    1. 房屋图片
    2. 判断是否有图片上传， 没有数据时返回错误信息
    3. 若有数据，则图区图片数据
    :return:
    """
    # 1.获取图片对象
    house_image = request.files.get('house_image')

    # 2. 判断图片数据是否为空
    if not house_image:
        return jsonify(errno=RET.DATAERR, errmsg='没有图片数据')
    # 校验house_id,查询对应的house信息
    try:
        house = House.query.filter_by(id=house_id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR, errmsg='查询房屋信息失败')
    if not house:
        return jsonify(errno=RET.DATAERR, errmsg='您查询的房屋不存在')
    # 3. 如果有图片数据时，
    house_image_data = house_image.read()

    # 4. 将图片数据上传到七牛云服务, 返回图片再七牛云上的图片名称
    try:
        image_name = storage(house_image_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg='上传图片信息失败')
    # 5. 将图片名称保存到数据库,包含house.index_image_url和HouseImage.url
    if not house.index_image_url:
        house.index_image_url = image_name
        db.session.add(house)
    house_image = HouseImage()
    house_image.house_id = house_id
    house_image.url = image_name
    db.session.add(house_image)
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='更新图片信息到数据库错误')
    # 拼接完整的url返回给浏览器
    image_url = constants.QINIU_DOMIN_PREFIX + image_name
    return jsonify(errno=RET.OK, errmsg='OK', data={'url': image_url})

