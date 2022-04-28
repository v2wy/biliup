from aiohttp import web
import os
from biliup.engine import config
from aiohttp_basicauth_middleware import basic_auth_middleware


async def get_basic_config(request):
    res = {
        "line": config.data['lines'],
        "limit": config.data['threads'],
        "user": {
            "SESSDATA": config.data['user']['cookies']['SESSDATA'],
            "bili_jct": config.data['user']['cookies']['bili_jct'],
            "DedeUserID__ckMd5": config.data['user']['cookies']['DedeUserID__ckMd5'],
            "DedeUserID": config.data['user']['cookies']['DedeUserID'],
            "access_token": config.data['user']['access_token'],
        }
    }
    return web.json_response(res)


async def set_basic_config(request):
    post_data = await request.json()
    config.data['lines'] = post_data['line']
    if config.data['lines'] == 'cos':
        config.data['lines'] = 'cos-internal'
    config.data['threads'] = post_data['limit']
    config.data['user']['cookies']['SESSDATA'] = post_data['user']['SESSDATA']
    config.data['user']['cookies']['bili_jct'] = post_data['user']['bili_jct']
    config.data['user']['cookies']['DedeUserID__ckMd5'] = post_data['user']['DedeUserID__ckMd5']
    config.data['user']['cookies']['DedeUserID'] = post_data['user']['DedeUserID']
    config.data['user']['access_token'] = post_data['user']['access_token']
    return web.json_response({"status": 200})


async def get_streamer_config(request):
    return web.json_response(config.data['streamers'])


async def set_streamer_config(request):
    post_data = await request.json()
    config.data['streamers'] = post_data['streamers']
    # for i,j in post_data['streamers'].items():
    #     if i not in config.data['streamers']:
    #         config.data['streamers'][i]={}
    #     for key,Value in j.items():
    #         config.data['streamers'][i][key]=Value
    # for i in config.data['streamers']:
    #     if i not in post_data['streamers']:
    #         del config.data['streamers'][i]

    print("sucess")
    return web.json_response({"status": 200}, status=200)


async def save_config(reequest):
    config.save()
    return web.json_response({"status": 200}, status=200)


async def root_handler(request):
    return web.HTTPFound('/index.html')


async def service(args, event_manager):

    async def url_status(request):
        return web.json_response(event_manager.context['KernelFunc'].get_url_status())
    app = web.Application()
    try:
        from importlib.resources import files
    except ImportError:
        # Try backported to PY<37 `importlib_resources`.
        from importlib_resources import files
    app.add_routes([web.get('/url-status', url_status)])
    app.add_routes([web.get('/api/basic', get_basic_config)])
    app.add_routes([web.post('/api/setbasic', set_basic_config)])
    app.add_routes([web.get('/api/getconfig', get_streamer_config)])
    app.add_routes([web.post('/api/setconfig', set_streamer_config)])
    app.add_routes([web.get('/api/save', save_config)])
    app.add_routes([web.get('/', root_handler)])
    if args.static_dir:
        app.add_routes([web.static('/', args.static_dir, show_index=False)])
    else:
        app.add_routes([web.static('/', files('biliup.web').joinpath('public'), show_index=False)])
        app.add_routes([web.static('/build', files('biliup.web').joinpath('public/build'), show_index=False)])
    if args.password:
        app.middlewares.append(basic_auth_middleware(('/',), {'biliup': args.password}, ))

    # web.run_app(app, host=host, port=port)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=args.host, port=args.port)
    return runner, site