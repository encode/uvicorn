from __future__ import annotations as _annotations

import os
import re
import subprocess
from collections import defaultdict
from typing import Literal, TypedDict, cast

import requests
from mkdocs.config import Config
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page


def on_page_content(html: str, page: Page, config: Config, files: Files) -> str:
    """Called on each page after the markdown is converted to HTML."""
    html = add_hyperlink_to_pull_request(html, page, config, files)
    return html


def add_hyperlink_to_pull_request(html: str, page: Page, config: Config, files: Files) -> str:
    """Add hyperlink on PRs mentioned on the release notes page.

    If we find "(#\\d+)" it will be added an hyperlink to https://github.com/encode/uvicorn/pull/$1.
    """
    if not page.file.name == "release-notes":
        return html

    return re.sub(r"\(#(\d+)\)", r"(<a href='https://github.com/encode/uvicorn/pull/\1'>#\1</a>)", html)


def on_page_markdown(markdown: str, page: Page, config: Config, files: Files) -> str:
    """Called on each file after it is read and before it is converted to HTML."""
    markdown = uvicorn_print_help(markdown, page)
    markdown = sponsors(markdown, page)
    return markdown


def uvicorn_print_help(markdown: str, page: Page) -> str:
    # if you don't filter to the specific route that needs this substitution, things will be very slow
    if page.file.src_uri not in ("index.md", "deployment.md"):
        return markdown

    output = subprocess.run(["uvicorn", "--help"], capture_output=True, check=True)
    logfire_help = output.stdout.decode()
    return re.sub(r"{{ *uvicorn_help *}}", logfire_help, markdown)


class Tier(TypedDict):
    id: str
    name: str
    isOneTime: bool
    monthlyPriceInDollars: int


class SponsorshipForViewerAsSponsorable(TypedDict):
    isActive: bool
    createdAt: str
    tier: Tier


class Sponsor(TypedDict):
    __typename: Literal["User", "Organization"]
    url: str
    avatarUrl: str
    bio: str
    login: str
    name: str
    sponsorshipForViewerAsSponsorable: SponsorshipForViewerAsSponsorable
    twitterUsername: str


class Viewer(TypedDict):
    login: str
    sponsors: dict[str, list[Sponsor]]
    sponsoring: dict[str, list[Sponsor]]
    sponsorsListing: dict[str, str]


class ResponseData(TypedDict):
    viewer: Viewer


class GitHubResponse(TypedDict):
    data: ResponseData


def sponsors(markdown: str, page: Page) -> str:
    if page.file.src_uri not in ("index.md"):
        return markdown

    GH_TOKEN = os.getenv("GH_TOKEN")
    # Retrieve Kludex sponsors from GitHub GraphQL API.
    response = requests.post(
        "https://api.github.com/graphql",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {GH_TOKEN}"},
        json={
            "query": """
{
  viewer {
    login
    ... on Sponsorable {
      sponsors(first: 100, orderBy: {field: RELEVANCE, direction: DESC}) {
        totalCount
        nodes {
          __typename
          ... on User {
            login
            name
            bio
            url
            avatarUrl
            twitterUsername
            sponsorshipForViewerAsSponsorable {
              isActive
              createdAt
              tier {
                id
                name
                isOneTime
                monthlyPriceInDollars
              }
            }
          }
          ... on Organization {
            login
            name
            description
            url
            avatarUrl
            twitterUsername
            sponsorshipForViewerAsSponsorable {
              isActive
              createdAt
              tier {
                id
                name
                isOneTime
                monthlyPriceInDollars
              }
            }
          }
        }
      }
    }
    sponsoring(first: 100) {
      nodes {
        __typename
        ... on User {
          login
          name
          bio
          url
          avatarUrl
          twitterUsername
          sponsorshipForViewerAsSponsor {
            isOneTimePayment
            isActive
            createdAt
            tier {
              id
              isCustomAmount
              monthlyPriceInDollars
              isOneTime
              name
              description
            }
          }
        }
        ... on Organization {
          login
          name
          description
          url
          avatarUrl
          twitterUsername
          sponsorshipForViewerAsSponsor {
            isOneTimePayment
            isActive
            createdAt
            tier {
              id
              isCustomAmount
              monthlyPriceInDollars
              isOneTime
              name
              description
            }
          }
        }
      }
    }
    sponsorsListing {
      url
      fullDescription
      activeGoal {
        kind
        description
        percentComplete
        targetValue
        title
      }
      tiers(first: 100) {
        nodes {
          id
          name
          isOneTime
          description
          monthlyPriceInDollars
          isCustomAmount
        }
      }
    }
  }
}
        """
        },
    )
    response.raise_for_status()
    data = cast(GitHubResponse, response.json())

    sponsor_tiers: defaultdict[str, list[Sponsor]] = defaultdict(list)
    for sponsor in data["data"]["viewer"]["sponsors"]["nodes"]:
        monthly_price_in_dollars = sponsor["sponsorshipForViewerAsSponsorable"]["tier"]["monthlyPriceInDollars"]
        if monthly_price_in_dollars >= 500:
            sponsor_tiers["gold"].append(sponsor)
        elif monthly_price_in_dollars >= 250:
            sponsor_tiers["silver"].append(sponsor)
        elif monthly_price_in_dollars >= 100:
            sponsor_tiers["bronze"].append(sponsor)
        else:
            sponsor_tiers["others"].append(sponsor)

    sponsors: list[str] = [
        "## 🚀 Gold sponsors",
        generate_sponsor_html(sponsor_tiers["gold"]),
    ]

    return re.sub(r"{{ *sponsors *}}", "\n".join(sponsors), markdown)


def generate_sponsor_html(sponsors: list[Sponsor]) -> str:
    content = """<div style="display: flex; flex-wrap: wrap;">"""

    for sponsor in sponsors:
        content += f"""
    <div style="margin: 10px; text-align: center; width: 120px;">
        <img src="{sponsor['avatarUrl']}" style="border-radius: 50%; width: 100px; height: 100px;">
        <div><a href="https://github.com/{sponsor['login']}">{sponsor['login']}</a></div>
    </div>
"""

    content += """\n</div>"""
    return content
