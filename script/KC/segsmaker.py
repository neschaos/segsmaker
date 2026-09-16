from IPython.display import clear_output
from IPython import get_ipython
from pathlib import Path
import subprocess
import argparse
import logging
import shutil
import shlex
import json
import yaml
import time
import os

from _segsmaker_ import HOME, SRC, UID
from cupang import Tunnel as Alice

SyS = get_ipython().system
iRON = os.environ

ROOT = Path.home()
CWD = Path.cwd()
PW = '82a973c04367123ae98bd9abdf80d9eda9b910e2'

MARK = SRC / 'marking.json'
ui = json.load(MARK.open()).get('ui')

KAGGLE = 'KAGGLE_DATA_PROXY_TOKEN' in iRON

def trashing():
    f = ['ckpt', 'lora', 'controlnet', 'svd', 'z123']
    for p in [HOME / ui] + [Path('/tmp') / d for d in f]:
        SyS(f'find {p} -type d -name .ipynb_checkpoints -exec rm -rf {{}} + > /dev/null 2>&1')

def NGROK_auth(token):
    yml = ROOT / '.config/ngrok/ngrok.yml'

    if yml.exists(): current_token = yaml.safe_load(yml.read_text()).get('agent', {}).get('authtoken')
    else: current_token = None

    if current_token != token: SyS(f'ngrok config add-authtoken {token}'); print()

def ZROK_enable(token):
    zrok_env = ROOT / '.zrok2/environment.json'
    e = f'zrok2 enable {token}'
    d = 'zrok2 disable'

    if zrok_env.exists():
        current_token = json.loads(zrok_env.read_text()).get('zrok_token')
        if current_token != token: SyS(d); SyS(e); print()

    else: SyS(e); print()

def webui_launch(
    launch_args,
    skip_comfyui_check,
    ngrok_token=None,
    zrok_token=None,
    use_gradio=True,
    use_pinggy=True,
    use_cloudflared=True,
    max_retries=3,
    retry_delay=5,
):
    iRON['PYTHONWARNINGS'] = 'ignore'

    if ui in ['ComfyUI', 'SwarmUI']:
        iRON['MPLBACKEND'] = 'agg'

        if ui == 'ComfyUI':
            cfg = HOME / 'ComfyUI/custom_nodes/was-node-suite-comfyui/was_suite_config.json'
            ffmpeg = shutil.which('ffmpeg')

            if cfg.exists() and ffmpeg:
                c = json.loads(cfg.read_text(encoding='utf-8'))
                c['ffmpeg_bin_path'] = ffmpeg
                cfg.write_text(json.dumps(c, indent=2), encoding='utf-8')

            skip_comfyui_check or (SyS('python3 apotek.py'), clear_output(wait=True))
            cmd = f'python3 main.py {launch_args}'

        else:
            for k, v in UID[ui].get('var', {}).items(): iRON[k] = v() if callable(v) else v
            cmd = f'bash ./launch-linux.sh {launch_args}'

    else:
        SyS(f"echo -n {int(time.time()) + 3600} > {CWD / 'asd/pinggytimer.txt'}")
        launch_args += ' --enable-insecure-extension-access --disable-console-progressbars --theme dark'

        if '--share' in launch_args: launch_args = launch_args.replace('--share', '')
        if KAGGLE: launch_args += f' --encrypt-pass={PW}'

        if ui == 'Forge' and not (CWD / 'FT.txt').exists():
            SyS('pip uninstall -qy transformers')
            (CWD / 'FT.txt').write_text('tf')

        if ui in ['ReForge', 'Forge-Neo']:
            iRON['MPLBACKEND'] = 'agg'

        iRON.setdefault('IIB_ACCESS_CONTROL', 'disable')
        iRON.setdefault('IIB_SKIP_OPTIONAL_DEPS', '1')

        cmd = f'python3 launch.py {launch_args}'

    port = UID[ui].get('port', 7860)

    cloudflared = f'cl tunnel --url localhost:{port}'
    pinggy = f'ssh -o StrictHostKeyChecking=no -p 80 -R0:localhost:{port} a.pinggy.io'
    ngrok = f'ngrok http http://localhost:{port} --log stdout'
    zrok2 = f'zrok2 share public localhost:{port} --headless'
    gradio = f'gradio-tun {port}'

    Zuberg = Alice(port, max_retries=max_retries, retry_delay=retry_delay)
    Zuberg.logger.setLevel(logging.DEBUG)
    Add = lambda command, name, pattern: Zuberg.add_tunnel(command=command, name=name, pattern=pattern)

    if use_gradio:
        Add(gradio, 'Gradio', r'https://[\w-]+\.gradio\.live')
    if use_pinggy:
        Add(pinggy, 'Pinggy', r'https://[\w-]+\.run\.pinggy-free\.link')
    if use_cloudflared:
        Add(cloudflared, 'Cloudflared', r'[\w-]+\.trycloudflare\.com')

    if ngrok_token:
        NGROK_auth(ngrok_token)
        Add(ngrok, 'NGROK', r'https://[\w-]+\.ngrok-free\.[\w.-]+')

    if zrok_token:
        ZROK_enable(zrok_token)
        Add(zrok2, 'ZROK2', r'[\w-]+\.shares\.zrok\.io')

    with Zuberg:
        SyS(cmd)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='nothing to read here')
    parser.add_argument('--skip-comfyui-check', action='store_true', help='Skip checking custom node dependencies for ComfyUI')
    parser.add_argument('--N', type=str, help='NGROK tunnel (pass a token or do nothing)', default=None)
    parser.add_argument('--Z', type=str, help='ZROK2 tunnel (pass a token or do nothing)', default=None)
    parser.add_argument('--no-gradio', action='store_true', help='Nao rodar o tunel Gradio')
    parser.add_argument('--no-pinggy', action='store_true', help='Nao rodar o tunel Pinggy')
    parser.add_argument('--no-cloudflared', action='store_true', help='Nao rodar o tunel Cloudflared')
    parser.add_argument('--max-retries', type=int, default=3, help='Quantas vezes tentar relançar um tunel que caiu sozinho')
    parser.add_argument('--retry-delay', type=int, default=5, help='Espera inicial (segundos) antes de tentar relançar um tunel; dobra a cada tentativa')

    args, unknown = parser.parse_known_args()
    launch_args = ' '.join(unknown)

    try:
        trashing()
        webui_launch(
            launch_args,
            args.skip_comfyui_check,
            ngrok_token=args.N,
            zrok_token=args.Z,
            use_gradio=not args.no_gradio,
            use_pinggy=not args.no_pinggy,
            use_cloudflared=not args.no_cloudflared,
            max_retries=args.max_retries,
            retry_delay=args.retry_delay,
        )
    except KeyboardInterrupt:
        pass
