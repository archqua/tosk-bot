import os


templates_dir = os.path.dirname(os.path.abspath(__file__))
# for exposure with fire module
script_registry = []


def script(func):
    script_registry.append((func.__name__, func))
    return func


@script
def pull(dockerhub_username="archqua", docker_image="tosk-bot", tag="stable"):
    pull_template_path = os.path.join(templates_dir, "tosk-bot.pull.template")
    with open(pull_template_path, "r") as fp:
        contents = fp.read()
    formatted = contents.format(
        dockerhub_username=dockerhub_username,
        docker_image=docker_image,
        tag=tag,
    )
    print(formatted, end="")


@script
def service(
    telegram_api_token,
    dockerhub_username="archqua",
    docker_image="tosk-bot",
    tag="stable",
):
    service_template_path = os.path.join(templates_dir, "tosk-bot.service.template")
    with open(service_template_path, "r") as fp:
        contents = fp.read()
    formatted = contents.format(
        telegram_api_token=telegram_api_token,
        dockerhub_username=dockerhub_username,
        docker_image=docker_image,
        tag=tag,
    )
    print(formatted, end="")


if __name__ == "__main__":
    import fire

    fire.Fire(dict(script_registry))
