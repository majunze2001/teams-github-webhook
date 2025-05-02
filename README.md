# A Github Webhook Proxy Server for Microsoft Teams

**Currently only supports tracking commits**

Example `.env`
```
PORT=8888
# quote the url otherwise some characters will get escaped
TEAMS_WEBHOOK_URL="your-webhook-url"
```

## About
- The official Github App in Microsoft Teams app is broken for me, as it does
not push notifications for new commit messages.
- The adaptive card doesn't have an API for the summary field in notifications,
please refer to [this issuse](https://github.com/MicrosoftDocs/msteams-docs/issues/11730#issuecomment-2476365809)
for a workaround.


## How to
1. Create a webhook workflow on Microsoft Teams, and save the webhook URL.
2. Deploy the server (next section) with the webhook URL.
3. Use the server endpoint (`example.com/webhook`) for your Github repo webhook.


## Deploy
You can deploy it on your server or on [Vercel](https://vercel.com). For Vercel,
you only need to put in the Teams webhook url for the environmental variable
(no quotation marks).
