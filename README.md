# tosk-bot
Studying containers and other stuff

## Usage
### Compose
See examples in `compose.yaml` (rabbitmq)
and `compose.override.yaml`.
`USERNAME` and `TAG` environment variables identify images to pull from dockerhub.
`TOSK_BOT_BASE_TELEGRAM_API_TOKEN` stores bot token.
```bash
TOSK_BOT_BASE_TELEGRAM_API_TOKEN=$(pass tosk-bot/api) USERNAME=archqua podman-compose up
```

There's a convenience `release.sh` script to create and push images to dockerhub
with configurable user name and tag.
It fetches metadata from `poetry` and `git` to set labels.
See `./release.sh -h` for usage.

## TODO
- [ ] use [RPC pattern](https://deepwiki.com/mosquito/aio-pika/5.1-rpc-pattern)
    to call API methods
- [ ] wait for responses during shutdown
- [ ] fix tests
