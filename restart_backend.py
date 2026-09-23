import docker
client = docker.from_env()
container = client.containers.get('edgemind-backend-1')
container.restart()
print("Backend restarted!")
