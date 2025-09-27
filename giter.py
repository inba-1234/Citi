"""
github_mcp_server.py
A simple MCP-style Python server that aggregates all GitHub details of a user.
Author: ChatGPT (GPT-5)

Run:
    pip install fastapi "uvicorn[standard]" requests
    uvicorn github_mcp_server:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import requests

app = FastAPI(
    title="GitHub MCP Server",
    description="Fetches all GitHub data (profile, repos, orgs, gists, events) for a user",
    version="1.0.0"
)

GITHUB_API_BASE = "https://api.github.com"


# --------- Models ---------
class GitHubUser(BaseModel):
    login: str
    name: str | None = None
    bio: str | None = None
    public_repos: int
    followers: int
    following: int
    created_at: str
    updated_at: str
    avatar_url: str
    html_url: str


class Repo(BaseModel):
    name: str
    html_url: str
    description: str | None = None
    stargazers_count: int
    forks_count: int
    language: str | None = None
    updated_at: str


class Organization(BaseModel):
    login: str
    description: str | None = None
    url: str
    avatar_url: str


class Gist(BaseModel):
    id: str
    html_url: str
    description: str | None = None
    created_at: str


class GitHubUserData(BaseModel):
    profile: GitHubUser
    repositories: list[Repo]
    organizations: list[Organization]
    gists: list[Gist]
    events: list[dict]


# --------- Helper Function ---------
def github_api_request(endpoint: str, token: str | None = None):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    resp = requests.get(f"{GITHUB_API_BASE}{endpoint}", headers=headers, timeout=10)
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="User or resource not found.")
    elif resp.status_code == 403:
        raise HTTPException(status_code=403, detail="API rate limit exceeded or access denied.")
    elif not resp.ok:
        raise HTTPException(status_code=resp.status_code, detail=f"GitHub API error: {resp.text}")
    return resp.json()



# --------- API Route for Repo Contents ---------
@app.get("/github/{username}/{repo}/contents")
def get_repo_contents_endpoint(username: str, repo: str):
    """Fetch the contents of a GitHub repository (files/folders in root)."""
    url = f"https://api.github.com/repos/{username}/{repo}/contents"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=f"GitHub API error: {response.text}")


# --------- API Route ---------
@app.get("/github/{username}", response_model=GitHubUserData)
def get_github_user(
    username: str,
    token: str | None = Query(None, description="Optional GitHub PAT for private or authenticated access")
):
    """Fetch full GitHub details for the given username."""

    # --- 1. Basic user info ---
    user_json = github_api_request(f"/users/{username}", token)
    print(user_json)
    profile = GitHubUser(**user_json)

    # --- 2. Repositories ---
    repos_json = github_api_request(f"/users/{username}/repos?per_page=100&sort=updated", token)
    repos = [
        Repo(
            name=r["name"],
            html_url=r["html_url"],
            description=r.get("description"),
            stargazers_count=r["stargazers_count"],
            forks_count=r["forks_count"],
            language=r.get("language"),
            updated_at=r["updated_at"]
        ) for r in repos_json
    ]

    # --- 3. Organizations ---
    # Use authenticated user's orgs endpoint if token is provided to get both public and private memberships
    if token:
        try:
            # Try to get authenticated user's organizations (includes private memberships)
            auth_user_json = github_api_request("/user", token)
            if auth_user_json["login"].lower() == username.lower():
                # If the token belongs to the requested user, get all their orgs (public + private)
                orgs_json = github_api_request("/user/orgs", token)
            else:
                # If token belongs to different user, fall back to public orgs only
                orgs_json = github_api_request(f"/users/{username}/orgs", token)
        except:
            # If there's any error with authenticated endpoints, fall back to public orgs
            orgs_json = github_api_request(f"/users/{username}/orgs", token)
    else:
        # No token provided, can only get public organizations
        orgs_json = github_api_request(f"/users/{username}/orgs", token)
    
    orgs = [
        Organization(
            login=o["login"],
            description=o.get("description"),
            url=o["url"],
            avatar_url=o["avatar_url"]
        ) for o in orgs_json
    ]

    # --- 4. Gists ---
    gists_json = github_api_request(f"/users/{username}/gists", token)
    gists = [
        Gist(
            id=g["id"],
            html_url=g["html_url"],
            description=g.get("description"),
            created_at=g["created_at"]
        ) for g in gists_json
    ]

    # --- 5. Events (recent activity) ---
    events_json = github_api_request(f"/users/{username}/events/public", token)

    return GitHubUserData(
        profile=profile,
        repositories=repos,
        organizations=orgs,
        gists=gists,
        events=events_json[:10]  # limit to last 10 events
    )




@app.get("/github/{username}/private-repos")
def get_private_repos(
    username: str,
    token: str = Query(..., description="GitHub PAT required for accessing private repositories")
):
    """
    Fetch only private repositories for the given username.
    Requires a valid GitHub Personal Access Token with repo scope.
    """
    if not token:
        raise HTTPException(
            status_code=400, 
            detail="GitHub token is required to access private repositories"
        )
    
    # Use authenticated user endpoint if username matches token owner, 
    # otherwise use user-specific endpoint
    try:
        # First, try to get user's own repos (this will include private ones if token belongs to user)
        repos_json = github_api_request(f"/user/repos?per_page=100&sort=updated&type=private", token)
        
        # Filter to only include repos owned by the specified username
        filtered_repos = []
        for repo in repos_json:
            if repo["owner"]["login"].lower() == username.lower() and repo["private"]:
                filtered_repos.append(repo)
        
        # If no repos found with user endpoint, try the public user endpoint 
        # (this won't show private repos but will verify user exists)
        if not filtered_repos:
            # Verify user exists
            github_api_request(f"/users/{username}", token)
            # Return empty list if user exists but no private repos accessible
            return []
        
        # Convert to Repo models
        private_repos = [
            Repo(
                name=r["name"],
                html_url=r["html_url"],
                description=r.get("description"),
                stargazers_count=r["stargazers_count"],
                forks_count=r["forks_count"],
                language=r.get("language"),
                updated_at=r["updated_at"]
            ) for r in filtered_repos
        ]
        
        return {
            "username": username,
            "private_repositories_count": len(private_repos),
            "private_repositories": private_repos
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching private repositories: {str(e)}")


@app.get("/github/{username}/metrics")
def get_github_metrics(
    username: str,
    token: str | None = Query(None, description="Optional GitHub PAT for authenticated access")
):
    """
    Aggregates useful GitHub metrics for recruiters:
    - Total public contributions (commits)
    - Pull requests raised
    - Issues opened
    - Stars received
    - Forks made
    """
    # Fetch repositories
    repos_json = github_api_request(f"/users/{username}/repos?per_page=100", token)
    total_commits = 0
    total_stars = 0
    total_forks = 0

    for repo in repos_json:
        # Commits: fetch commit count for each repo
        commits_url = f"/repos/{username}/{repo['name']}/commits?per_page=1"
        commits_resp = requests.get(f"{GITHUB_API_BASE}{commits_url}", headers={"Accept": "application/vnd.github+json"}, timeout=10)
        if "Link" in commits_resp.headers:
            # Parse last page from Link header for total commits
            import re
            match = re.search(r'&page=(\d+)>; rel="last"', commits_resp.headers["Link"])
            if match:
                total_commits += int(match.group(1))
            else:
                total_commits += 1
        else:
            total_commits += len(commits_resp.json())
        total_stars += repo.get("stargazers_count", 0)
        total_forks += repo.get("forks_count", 0)

    # Pull requests raised
    pulls_json = github_api_request(f"/search/issues?q=author:{username}+type:pr", token)
    total_pull_requests = pulls_json.get("total_count", 0)

    # Issues opened
    issues_json = github_api_request(f"/search/issues?q=author:{username}+type:issue", token)
    total_issues = issues_json.get("total_count", 0)

    return {
        "username": username,
        "total_public_repos": len(repos_json),
        "total_commits": total_commits,
        "total_pull_requests": total_pull_requests,
        "total_issues_opened": total_issues,
        "total_stars_received": total_stars,
        "total_forks_made": total_forks
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}
