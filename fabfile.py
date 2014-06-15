import os
from StringIO import StringIO

from fabric.api import task, local, run
from fabric.contrib.files import exists
from fabric.operations import require, put
from fabric.state import env

from gitric.api import git_seed, git_reset, allow_dirty, force_push  # noqa


# live/
#   env/
#   repo/
#   etc/
#     pid
#     nginx.conf
# next/
#   env/
#   repo/
#   etc/
#     pid
#     nginx.conf


def init_bluegreen():
    require('bluegreen_root', 'bluegreen_ports')
    env.green_path = os.path.join(env.bluegreen_root, 'green')
    env.blue_path = os.path.join(env.bluegreen_root, 'blue')
    env.next_path_abs = os.path.join(env.bluegreen_root, 'next')
    env.live_path_abs = os.path.join(env.bluegreen_root, 'live')
    run('mkdir -p %(bluegreen_root)s %(blue_path)s %(green_path)s '
        '%(blue_path)s/etc %(green_path)s/etc' % env)
    if not exists(env.live_path_abs):
        run('ln -s %(blue_path)s %(live_path_abs)s' % env)
    if not exists(env.next_path_abs):
        run('ln -s %(green_path)s %(next_path_abs)s' % env)
    env.next_path = run('readlink -f %(next_path_abs)s' % env)
    env.live_path = run('readlink -f %(live_path_abs)s' % env)
    env.virtualenv_path = os.path.join(env.next_path, 'env')
    env.pidfile = os.path.join(env.next_path, 'etc', 'app.pid')
    env.nginx_conf = os.path.join(env.next_path, 'etc', 'nginx.conf')
    env.color = os.path.basename(env.next_path)
    env.bluegreen_port = env.bluegreen_ports.get(env.color)


@task
def prod():
    env.user = 'test-deployer'
    env.bluegreen_root = '/home/test-deployer/bluegreenmachine/'
    env.bluegreen_ports = {'blue': '8888',
                           'green': '8889'}
    init_bluegreen()


@task
def deploy(commit=None):
    if not commit:
        commit = local('git rev-parse HEAD', capture=True)
    env.repo_path = os.path.join(env.next_path, 'repo')
    git_seed(env.repo_path, commit)
    git_reset(env.repo_path, commit)
    run('kill $(cat %(pidfile)s) || true' % env)
    run('virtualenv %(virtualenv_path)s' % env)
    run('source %(virtualenv_path)s/bin/activate && '
        'pip install -r %(repo_path)s/requirements.txt' % env)
    put(StringIO('proxy_pass http://127.0.0.1:%(bluegreen_port)s/;' % env),
        env.nginx_conf)
    run('cd %(repo_path)s && PYTHONPATH=. BLUEGREEN=%(color)s '
        '%(virtualenv_path)s/bin/gunicorn -D '
        '-b 0.0.0.0:%(bluegreen_port)s -p %(pidfile)s app:app' %
        env)


@task
def cutover():
    require('next_path', 'live_path', 'live_path_abs', 'next_path_abs')
    run('ln -nsf %(next_path)s %(live_path_abs)s' % env)
    run('ln -nsf %(live_path)s %(next_path_abs)s' % env)
    run('sudo /etc/init.d/nginx reload')
