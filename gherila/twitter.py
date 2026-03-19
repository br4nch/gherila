from json import dumps

from .exceptions import Error
from .http import State
from .models import (
  TwitterUser,
  TwitterUserBiolinks
)

class Twitter:
  def __init__(self: "Twitter", auth_token: str, ct0: str, crsf: str, authorization: str):
    self.session = State()
    self.headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
      "Authorization": authorization,
      "X-Csrf-Token": crsf,
      "Cookie": f"auth_token={auth_token}; ct0={ct0}"
      }
  
  async def get_user(self: "Twitter", username: str):
    """
    Get a twitter (x.com) user information.

    Parameters
    ----------
    username : :class:`str`
      The twitter (x.com) account username.

    Returns
    -------
    :class:`TwitterUser`
      A TwitterUser object with the found information.
    """
    data = await self.session.request(
      "GET",
      f"https://x.com/i/api/graphql/IGgvgiOx4QZndDHuD3x9TQ/UserByScreenName",
      headers=self.headers,
      params = {
        "variables": dumps(
          {
            "screen_name": username,
            "withGrokTranslatedBio": False,
          }
        ),
        "features": dumps(
          {
            "hidden_profile_subscriptions_enabled": True,
            "profile_label_improvements_pcf_label_in_post_enabled": True,
            "responsive_web_profile_redirect_enabled": False,
            "rweb_tipjar_consumption_enabled": False,
            "verified_phone_label_enabled": False,
            "subscriptions_verification_info_is_identity_verified_enabled": True,
            "subscriptions_verification_info_verified_since_enabled": True,
            "highlights_tweets_tab_ui_enabled": True,
            "responsive_web_twitter_article_notes_tab_enabled": True,
            "subscriptions_feature_can_gift_premium": True,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True
          }
        ),
        "fieldToggles": dumps(
          {
            "withPayments": False,
            "withAuxiliaryUserLabels": True,
          }
        )
      }
    )

    if not data.data:
      raise Error(f"No x account found for given username `{username}`.")

    core = data.data.user.result.core
    stats = data.data.user.result
    legacy = data.data.user.result.legacy
    biolinks = []

    for entity in legacy.get("entities", {}).values():
      if "urls" in entity:
        for link in entity.get("urls", []):
          if "expanded_url" in link:
            biolinks.append(
              TwitterUserBiolinks(**link)
            )

    return TwitterUser(
      username=username,
      id=stats.rest_id,
      avatar=stats.avatar.image_url,
      bio=legacy.description,
      display_name=core.name,
      location=stats.location.location,
      verified=stats.is_blue_verified,
      created_at=core.created_at,
      followers=legacy.followers_count,
      following=legacy.friends_count,
      posts=legacy.media_count,
      liked_posts=legacy.favourites_count,
      tweets=legacy.statuses_count,
      biolinks=biolinks,
      url=f"https://x.com/{username}"
    )