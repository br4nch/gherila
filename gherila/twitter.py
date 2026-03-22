from re import compile
from json import dumps
from urllib.parse import urlparse
from unicodedata import normalize

from .exceptions import Error
from .http import State
from .models import (
  TwitterUser,
  TwitterUserBiolinks,
  TwitterTweet,
  TwitterMedia
)

TWITTER_REGEX = r'https?:\/\/(www\.)?(twitter\.com|x\.com)\/[A-Za-z0-9_]{1,15}\/status\/\d+'
TWITTER_CONTENT = compile(TWITTER_REGEX)

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
      banner=legacy.profile_banner_url,
      bio=legacy.description,
      display_name=core.name,
      location=stats.location.location,
      verified=stats.is_blue_verified,
      verified_type=stats.verification.verified_type,
      created_at=core.created_at,
      followers=legacy.followers_count,
      following=legacy.friends_count,
      posts=legacy.media_count,
      liked_posts=legacy.favourites_count,
      tweets=legacy.statuses_count,
      pinned_tweets=legacy.pinned_tweet_ids_str,
      biolinks=biolinks,
      url=f"https://x.com/{username}"
    )

  async def get_tweet(self: "Twitter", url: str):
    """
    Get a twitter post information.

    Parameters
    ----------
    url : :class:`str`
      The url of the twitter post

    Returns
    -------
    :class:`TwitterTweet`
      A TwitterTweet object containing the results.
    """
    if not TWITTER_CONTENT.match(url):
      raise Error(f"This is not a valid tweet url.")

    tweetid = [p for p in urlparse(url).path.split('/') if p][2]

    data = await self.session.request(
      "GET",
      "https://x.com/i/api/graphql/xIYgDwjboktoFeXe_fgacw/TweetDetail",
      headers=self.headers,
      params={
        "variables": dumps(
          {
            "focalTweetId": tweetid,
            "reffer": "home",
            "with_rux_injections": False,
            "rankingMode": "Relevance",
            "includePromotedContent": True,
            "withCommunity": True,
            "withQuickPromoteEligibilityTweetFields": True,
            "withBirdwatchNotes": True,
            "withVoice": True
          }
        ),
        "features": dumps(
          {
            "rweb_video_screen_enabled": False,
            "profile_label_improvements_pcf_label_in_post_enabled": True,
            "responsive_web_profile_redirect_enabled": False,
            "rweb_tipjar_consumption_enabled": False,
            "verified_phone_label_enabled": False,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "premium_content_api_read_enabled": False,
            "communities_web_enable_tweet_community_results_fetch": True,
            "c9s_tweet_anatomy_moderator_badge_enabled": True,
            "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
            "responsive_web_grok_analyze_post_followups_enabled": True,
            "responsive_web_jetfuel_frame": True,
            "responsive_web_grok_share_attachment_enabled": True,
            "responsive_web_grok_annotations_enabled": True,
            "articles_preview_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": True,
            "tweet_awards_web_tipping_enabled": False,
            "content_disclosure_indicator_enabled": True,
            "content_disclosure_ai_generated_indicator_enabled": True,
            "responsive_web_grok_show_grok_translated_post": False,
            "responsive_web_grok_analysis_button_from_backend": True,
            "post_ctas_fetch_enabled": True,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": False,
            "responsive_web_grok_image_annotation_enabled": True,
            "responsive_web_grok_imagine_annotation_enabled": True,
            "responsive_web_grok_community_note_auto_translation_is_enabled": False,
            "responsive_web_enhance_cards_enabled": False
          }
        ),
        "fieldToggles": dumps(
          {
            "withArticleRichContentState": True,
            "withArticlePlainText": False,
            "withArticleSummaryText": True,
            "withArticleVoiceOver": True,
            "withGrokAnalyze": False,
            "withDisallowedReplyControls": False
          }
        )
      }
    )

    result = next(
      (
        entry.content.itemContent.tweet_results.result
        for instruction in data.data.threaded_conversation_with_injections_v2.instructions
        if instruction.type == "TimelineAddEntries"
        for entry in instruction.entries
        if entry.entryId == f"tweet-{tweetid}"
      ),
      None
    )
    user = await self.get_user(result.core.user_results.result.core.screen_name)
    legacy = result.legacy
    text = normalize(
      "NFKC",
      (
        result.note_tweet.note_tweet_results.result.text
        if "note_tweet" in result
        else legacy.full_text
      )
    )
    quote_url=(
      legacy.quoted_status_permalink.expanded
      if "quoted_status_permalink" in legacy 
      else None
    )

    medias = []
    if "extended_entities" in legacy:
      for m in legacy.extended_entities.media:
        media = TwitterMedia(type=m.type)

        if "video_info" in m:
          mp4 = [
            v
            for v in m.video_info.variants
            if getattr(v, "content_type", "") == "video/mp4"
          ]
          if mp4:
            media.video_url = sorted(
              mp4,
              key=lambda x: x.bitrate,
            )[-1].url

        if m.type == "photo":
          media.image_url = m.media_url_https

        medias.append(media)

    return TwitterTweet(
      id=tweetid,
      text=text,
      author=user,
      lang=legacy.lang,
      likes=legacy.favorite_count,
      replies=legacy.reply_count,
      retweets=legacy.retweet_count,
      quote=legacy.quote_count,
      retweeted=legacy.retweeted,
      created_at=legacy.created_at,
      views=result.views.count,
      bookmarks=legacy.bookmark_count,
      is_quote=legacy.is_quote_status,
      quote_url=quote_url,
      hashtags=[h.text for h in legacy.entities.hashtags],
      mentions=[m.screen_name for m in legacy.entities.user_mentions],
      media=medias
    )

  async def get_user_tweets(self: "Twitter", username: str):
    """
    Get 20 tweets of an user account.

    Parameters
    ----------
    username : :class:`str`
      The twitter account username.

    Returns
    -------
    :class:`List[TwitterTweet]`
      A TwitterTweet list containing the data.
    """
    user = await self.get_user(username)
    data = await self.session.request(
      "GET",
      f"https://x.com/i/api/graphql/O0epvwaQPUx-bT9YlqlL6w/UserTweets",
      headers=self.headers,
      params={
        "variables": dumps(
          {
            "userId": user.id,
            "count": 20,
            "includePromotedContent": True,
            "withQuickPromoteEligibilityTweetFields": True,
            "withVoice": True,
          }
        ),
        "features": dumps(
          {
            "rweb_video_screen_enabled": False,
            "profile_label_improvements_pcf_label_in_post_enabled": True,
            "responsive_web_profile_redirect_enabled": False,
            "rweb_tipjar_consumption_enabled": False,
            "verified_phone_label_enabled": False,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "premium_content_api_read_enabled": False,
            "communities_web_enable_tweet_community_results_fetch": True,
            "c9s_tweet_anatomy_moderator_badge_enabled": True,
            "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
            "responsive_web_grok_analyze_post_followups_enabled": True,
            "responsive_web_jetfuel_frame": True,
            "responsive_web_grok_share_attachment_enabled": True,
            "responsive_web_grok_annotations_enabled": True,
            "articles_preview_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": True,
            "tweet_awards_web_tipping_enabled": False,
            "content_disclosure_indicator_enabled": True,
            "content_disclosure_ai_generated_indicator_enabled": True,
            "responsive_web_grok_show_grok_translated_post": False,
            "responsive_web_grok_analysis_button_from_backend": True,
            "post_ctas_fetch_enabled": True,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": False,
            "responsive_web_grok_image_annotation_enabled": True,
            "responsive_web_grok_imagine_annotation_enabled": True,
            "responsive_web_grok_community_note_auto_translation_is_enabled": False,
            "responsive_web_enhance_cards_enabled": False
          }
        ),
        "fieldToggles": dumps(
          {
            "withArticlePlainText": False
          }
        )
      }
    )

    entries = next(
      (
        instruction.entries
        for instruction in data.data.user.result.timeline.timeline.instructions
        if instruction.type == "TimelineAddEntries"
      ),
      None
    )
    tweets = []

    for entry in entries:
      if entry.entryId.startswith("tweet-"):
        result = entry.content.itemContent.tweet_results.result
        if (
          legacy := result.legacy
        ):
          text = normalize(
            "NFKC",
            (
              result.note_tweet.note_tweet_results.result.text
              if "note_tweet" in result
              else legacy.full_text
            )
          )
          quote_url = (
            legacy.quoted_status_permalink.expanded
            if "quoted_status_permalink" in legacy 
            else None
          )

          medias = []
          if "extended_entities" in legacy:
            for m in legacy.extended_entities.media:
              media = TwitterMedia(type=m.type)

              if "video_info" in m:
                mp4 = [
                  v
                  for v in m.video_info.variants
                  if getattr(v, "content_type", "") == "video/mp4"
                ]
                if mp4:
                  media.video_url = sorted(
                    mp4,
                    key=lambda x: x.bitrate,
                  )[-1].url

              if m.type == "photo":
                media.image_url = m.media_url_https

              medias.append(media)

          tweets.append(
          TwitterTweet(
            id=legacy.id_str,
            text=text,
            author=user,
            lang=legacy.lang,
            likes=legacy.favorite_count,
            replies=legacy.reply_count,
            retweets=legacy.retweet_count,
            quote=legacy.quote_count,
            retweeted=legacy.retweeted,
            created_at=legacy.created_at,
            views=result.views.count if "views" in result else "0",
            bookmarks=legacy.bookmark_count,
            is_quote=legacy.is_quote_status,
            quote_url=quote_url,
            hashtags=[h.text for h in legacy.entities.hashtags] if "hashtags" in legacy.entities else [],
            mentions=[m.screen_name for m in legacy.entities.user_mentions] if "user_mentions" in legacy.entities else [],
            media=medias
          )
        )

    return tweets