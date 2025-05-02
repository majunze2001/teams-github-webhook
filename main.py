from mangum import Mangum
import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

app = FastAPI(title="GitHub to Teams Webhook", version="1.0.0")
PORT = int(os.environ.get("PORT", 8888))


# Configuration
class Settings:
    """Application settings."""

    def __init__(self):
        self.teams_webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")
        if not self.teams_webhook_url:
            logger.warning("TEAMS_WEBHOOK_URL environment variable not set")
            raise ValueError("TEAMS_WEBHOOK_URL environment variable not set")

    def get_teams_webhook_url(self) -> str:
        """Get the Microsoft Teams webhook URL."""
        assert self.teams_webhook_url, "TEAMS_WEBHOOK_URL not set"
        return self.teams_webhook_url


# Dependency to get settings
def get_settings() -> Settings:
    """Dependency to get application settings."""
    return Settings()


# Models
class CommitAuthor(BaseModel):
    """GitHub commit author."""

    name: str
    email: str
    username: Optional[str] = None


class Commit(BaseModel):
    """GitHub commit."""

    id: str
    message: str
    timestamp: str
    url: str
    author: CommitAuthor


class Repository(BaseModel):
    """GitHub repository."""

    full_name: str
    html_url: str


class GitHubWebhookPayload(BaseModel):
    """GitHub webhook payload."""

    ref: str
    repository: Repository
    commits: List[Commit]
    compare: Optional[str] = None


# Service layer
class TeamsNotifier:
    """Service for sending notifications to Microsoft Teams."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send_notification(
        self, teams_payload: Dict[str, Any], count: int, author: str
    ) -> bool:
        """Send notification to Microsoft Teams."""
        if not self.webhook_url:
            logger.error("Microsoft Teams webhook URL not configured")
            raise ValueError("Microsoft Teams webhook URL not configured")

        try:
            # Use aiohttp for async HTTP requests
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, json=teams_payload
                ) as response:
                    if response.status == 202:
                        logger.info(
                            "Successfully pushed %d commit(s) by %s to Teams",
                            count,
                            author,
                        )
                        return True
                    else:
                        response_text = (
                            await response.text()
                        )  # Need to await response.text()
                        logger.error(
                            f"Failed to send webhook to Teams: {response.status} - {response_text}"
                        )
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to send webhook to Teams: {response.status}",
                        )
        except aiohttp.ClientError as e:
            logger.exception(f"Error sending Teams notification: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error sending Teams notification: {str(e)}"
            )


class GitHubWebhookHandler:
    """Handler for GitHub webhook events."""

    @staticmethod
    def extract_branch_name(ref: str) -> str:
        """Extract branch name from GitHub ref."""
        return ref.replace("refs/heads/", "")

    @staticmethod
    def format_teams_payload(
        payload: GitHubWebhookPayload,
    ) -> tuple[Dict[str, Any], int, str]:
        """Format GitHub webhook data as Microsoft Teams message."""
        branch = GitHubWebhookHandler.extract_branch_name(payload.ref)
        commits = payload.commits
        commit_count = len(commits)

        # Get the author of the latest commit
        if commits:
            latest_author = commits[0].author.name
            author_username = commits[0].author.username
            author_url = (
                f"https://github.com/{author_username}" if author_username else ""
            )
        else:
            latest_author = "Unknown"
            author_url = ""

        text_blocks = []
        # Create the main text block
        if commit_count == 1:
            main_text = f"[1 new commit]({payload.compare}) pushed to `{branch}` by [{latest_author}]({author_url})"
            summary = f"1 new commit pushed to `{branch}` by {latest_author}"
        else:
            main_text = f"[{commit_count} new commits]({payload.compare}) pushed to `{branch}` by [{latest_author}]({author_url})"
            summary = (
                f"{commit_count} new commits pushed to `{branch}` by {latest_author}"
            )

        main_block = {"type": "TextBlock", "text": main_text, "wrap": True}
        text_blocks.append(main_block)

        repo_block = {
            "type": "TextBlock",
            "text": f"[{payload.repository.full_name}]({payload.repository.html_url})",
            "isSubtle": True,
            "wrap": True,
            "size": "small",
        }
        text_blocks.append(repo_block)

        # Create commit list text
        commit_text = ""
        for commit in commits:
            commit_id = commit.id[:8]  # First 8 characters of commit hash
            commit_message = commit.message
            commit_text += f"- _{commit_id}_ - {commit_message}\r"

        commit_list_block = {
            "type": "TextBlock",
            "text": commit_text,
            "wrap": True,
            "size": "medium",
        }
        text_blocks.append(commit_list_block)

        # Create the Microsoft Teams message card
        return (
            {
                "type": "message",
                "summary": summary,
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "contentUrl": None,
                        "content": {
                            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                            "type": "AdaptiveCard",
                            "version": "1.2",
                            "body": text_blocks,
                        },
                    }
                ],
            },
            commit_count,
            latest_author,
        )


# Middleware
@app.middleware("http")
async def verify_github_webhook(request: Request, call_next):
    """Middleware to verify GitHub webhook requests."""
    if request.url.path == "/webhook" and request.method == "POST":
        if not request.headers.get("X-GitHub-Event"):
            logger.warning("Received non-GitHub webhook request")
            return JSONResponse(
                content={"error": "This endpoint is for GitHub webhooks only"},
                status_code=400,
            )

    response = await call_next(request)
    return response


# Routes
@app.post("/webhook")
async def github_webhook(request: Request, settings: Settings = Depends(get_settings)):
    """Handle GitHub webhook POST requests."""
    try:
        # Parse JSON payload
        payload_dict = await request.json()
        if not payload_dict:
            logger.error("Received empty payload")
            raise HTTPException(status_code=400, detail="Empty payload")

        # Validate payload structure
        try:
            payload = GitHubWebhookPayload(**payload_dict)
        except Exception as e:
            logger.error(f"Invalid payload structure: {str(e)}")
            raise HTTPException(
                status_code=400, detail=f"Invalid payload structure: {str(e)}"
            )

        # Process the webhook
        teams_webhook_url = settings.get_teams_webhook_url()
        if not teams_webhook_url:
            raise HTTPException(
                status_code=500, detail="Microsoft Teams webhook URL not configured"
            )

        # Format Teams payload
        teams_payload, count, author = GitHubWebhookHandler.format_teams_payload(
            payload
        )

        # Send notification to Teams
        notifier = TeamsNotifier(teams_webhook_url)
        await notifier.send_notification(teams_payload, count, author)

        return {"status": "success"}

    except HTTPException:
        # Re-raise HTTP exceptions as they already have status codes
        raise
    except ValueError as e:
        # Configuration errors
        logger.error(f"Configuration error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        # Unexpected errors
        logger.exception(f"Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error processing webhook: {str(e)}"
        )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


handler = Mangum(app)

# Main entrypoint
if __name__ == "__main__":
    import uvicorn

    # For production, use:
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        workers=1,
        log_level="info",
        access_log=True,
        use_colors=False,
    )
