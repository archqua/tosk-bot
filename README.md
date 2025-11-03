# tosk-bot
Studying containers and other stuff

## Usage
### Docker
```bash
docker pull archqua/tosk-bot:stable
docker run --name tosk-bot \
    [--log-opt max-size=16m] \
    -e TOSK_BOT_TELEGRAM_API_TOKEN=<TELEGRAM_API_TOKEN> \
    archqua/tosk-bot:stable
docker rmi tosk-bot
```

There's a convenience `docker-publish.sh` script to create and push images to dockerhub
with configurable user name, docker image and tag.

Instead of `-e TOSK_BOT_TELEGRAM_API=...` can use
`--env-file path/to/pydantic/env`.


### Create ignition config
Requires [butane](https://docs.fedoraproject.org/en-US/fedora-coreos/producing-ign/)
```bash
poetry run python butane/tosk-bot.py butane <SSH_KEY> <TELEGRAM_API_TOKEN> | \
    butane --pretty --strict -o path/to/ignition/config.ign
```

E. g.
```bash
poetry run python butane/tosk-bot.py butane \
    "$(cat $HOME/.ssh/key.pub)" \
    "$(pass tosk-bot/api)" | \
    butane --pretty --strict -o path/to/ignition/config.ign
```

For more options
```bash
poetry run python butane/tosk-bot.py butane --help
NAME
    tosk-bot.py butane

SYNOPSIS
    tosk-bot.py butane SSH_KEY TELEGRAM_API_TOKEN <flags>

POSITIONAL ARGUMENTS
    SSH_KEY
    TELEGRAM_API_TOKEN

FLAGS
    --debug=DEBUG
        Default: False
    --dockerhub_username=DOCKERHUB_USERNAME
        Default: 'archqua'
    --docker_image=DOCKER_IMAGE
        Default: 'tosk-bot'
    -t, --tag=TAG
        Default: 'stable'

NOTES
    You can also use flags syntax for POSITIONAL ARGUMENTS
```

[Tutorials](https://docs.fedoraproject.org/en-US/fedora-coreos/tutorial-setup/) show how to use ignition configs
