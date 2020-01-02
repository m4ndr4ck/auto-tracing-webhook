import jsonpatch
from flask import Flask, request, jsonify
import copy
import logging
import base64
import os
import sys



JAEGER_ENV = {
    'JAEGER_AGENT_PORT': os.environ['JAEGER_AGENT_PORT'],
    'JAEGER_AGENT_HOST': os.environ['JAEGER_AGENT_HOST'],
    'JAEGER_SAMPLER_TYPE': 'const',
    'JAEGER_SAMPLER_PARAM': '1'
}

JAVA_AGENT = ' -javaagent:/mnt/auto-trace/opentracing-specialagent-1.5.0.jar -Dsa.tracer=jaeger -Dsa.log.level=FINE'

PROBE_DELAY = 300
PROBE_PERIOD = 30

app = Flask(__name__)

@app.route('/decorate', methods=['POST'])
def decorate():
    payload = request.get_json()
    req = payload['request']
    source = req['object']
    target = copy.deepcopy(source)

    logging.info(target)
    
    if target['metadata']['labels'].get('autotrace', 'disabled') == 'enabled':
        add_volume(target)
        add_init_container(target)
        tweak_containers(target)

    patch = jsonpatch.JsonPatch.from_diff(source, target)
    logging.info(patch)

    return jsonify({
        'response': {
            'uid': req['uid'],
            'allowed': True,
            'patchType': 'JSONPatch',
            'patch': base64.b64encode(str(patch).encode()).decode(),

        }
    })


def tweak_containers(target):
    containers = target['spec'].get('containers', [])
    for container in containers:
        add_mount(container)
        edit_env(container)
        extend_probe(container.get('livenessProbe', {}))
        extend_probe(container.get('readinessProbe', {}))

        
def extend_probe(probe):
    if probe.get('initialDelaySeconds', 0) < PROBE_DELAY:
        probe['initialDelaySeconds'] = PROBE_DELAY
    if probe.get('periodSeconds', 0) < PROBE_PERIOD:
        probe['periodSeconds'] = PROBE_PERIOD


def edit_env(container):
    env = container.get('env', [])
    for key, val in JAEGER_ENV.items():
        env.append({
            'name': key,
            'value': val
        })
    env.append({
        'name': 'JAEGER_SERVICE_NAME',
        'value': container['name']
    })

    add_java_agent(env)

    container['env'] = env


def add_java_agent(env):
    existing = [e for e in env if e['name'] == 'JAVA_TOOL_OPTIONS']
    if existing:
        existing = existing[0]
        existing['value'] = existing['value'] + JAVA_AGENT
    else:
        env.append({
            'name': 'JAVA_TOOL_OPTIONS',
            'value': JAVA_AGENT
        })


def add_mount(container):
    mounts = container.get('volumeMounts', [])
    mounts.append({
        'mountPath': '/mnt/auto-trace',
        'name': 'auto-trace-mount'
    })
    container['volumeMounts'] = mounts


def add_init_container(target):
    inits = target['spec'].get('initContainers', [])
    inits.append({
        'name': 'autotrace-additions',
        'image': 's4intlaurent/autotracing-sidecar:1.5.0',
        'volumeMounts': [{
            'mountPath': '/mnt/shared',
            'name': 'auto-trace-mount'
        }]
    })
    target['spec']['initContainers'] = inits


def add_volume(target):
    volumes = target['spec'].get('volumes', [])
    volumes.append({
        'name': 'auto-trace-mount',
        'emptyDir': {}
    })
    target['spec']['volumes'] = volumes


if __name__ == "__main__":
    app.run('0.0.0.0', debug=True, ssl_context=('webhook-server-tls.crt', 'webhook-server-tls.key'))
