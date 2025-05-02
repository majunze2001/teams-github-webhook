# A Github Webhook Proxy Server for Microsoft Teams

**Currently only support commit**

Example `.env`
```
PORT=8888
TEAMS_WEBHOOK_URL="your-webhook-url" # quote the url otherwise some characters will get escaped
```

## About
- The official Github App in Microsoft Teams app is broken for, as it would not push notifications
for new commit messages.
- The adaptive card doesn't have an API for the summary field in notifications, please refer to 
[this issuse](https://github.com/MicrosoftDocs/msteams-docs/issues/11730#issuecomment-2476365809)
for workaround


## Deploy
This app is ready to be deployed with [Vercel](https://vercel.com). You only need to put in the Teams
webhook url for the environmental variable (no quotation marks).
