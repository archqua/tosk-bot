# tosk-bot
Studying containers and other stuff

## Usage
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
poetry run python butane/tosk-bot.py --help
```

[Tutorials](https://docs.fedoraproject.org/en-US/fedora-coreos/tutorial-setup/) show how to use ignition configs
