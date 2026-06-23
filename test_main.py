import inspect
import unittest
from unittest.mock import AsyncMock, patch

import main


class NewsHelpersTests(unittest.TestCase):
    def test_build_newsdata_url_uses_query_and_api_key(self):
        with patch.object(main, "NEWSDATA_API_KEY", "demo-key"), patch.object(main, "NEWS_QUERY", "forex usd"):
            url = main.build_newsdata_url()

        self.assertIn("apikey=demo-key", url)
        self.assertIn("q=forex+usd", url)

    def test_build_newsapi_url_uses_query_and_api_key(self):
        with patch.object(main, "NEWS_API_KEY", "demo-key"), patch.object(main, "NEWS_QUERY", "forex usd"):
            url = main.build_newsapi_url()

        self.assertIn("apiKey=demo-key", url)
        self.assertIn("q=forex+usd", url)

    def test_get_active_provider_prefers_explicit_provider(self):
        with patch.object(main, "NEWS_PROVIDER", "newsdata"), patch.object(main, "NEWS_API_KEY", "demo"):
            self.assertEqual(main.get_active_provider(), "newsdata")

    def test_get_active_provider_uses_newsapi_when_key_exists(self):
        with patch.object(main, "NEWS_PROVIDER", "auto"), patch.object(main, "NEWS_API_KEY", "demo"):
            self.assertEqual(main.get_active_provider(), "newsapi")

    def test_is_forex_relevant_detects_currency_news(self):
        article = {"title": "Dollar rises as Fed signals another hike"}

        self.assertTrue(main.is_forex_relevant(article))

    def test_infer_bias_signal_detects_bullish_usd(self):
        article = {"title": "Dollar gains after hawkish Fed comments"}

        self.assertEqual(main.infer_bias_signal(article), "Bullish USD")

    def test_format_article_message_includes_bias_and_link(self):
        article = {
            "title": "Dollar gains after hawkish Fed comments",
            "source_name": "Reuters",
            "pubDate": "2026-06-23 10:00:00",
            "description": "The US dollar climbed after stronger inflation data.",
            "link": "https://example.com/story",
        }

        with patch.object(main, "ai_analyze_news", return_value=None):
            message = main.format_article_message(article)

        self.assertIn("FOREX SIGNAL", message)
        self.assertIn("Market Trend", message)
        self.assertIn("https://example.com/story", message)

    def test_load_newsdata_articles_returns_results(self):
        payload = {"status": "success", "results": [{"title": "A"}, {"title": "B"}]}

        articles = main.load_newsdata_articles(payload)

        self.assertEqual(len(articles), 2)

    def test_load_newsapi_articles_normalizes_results(self):
        payload = {
            "status": "ok",
            "articles": [
                {
                    "title": "Dollar rises",
                    "description": "USD gains",
                    "url": "https://example.com/a",
                    "publishedAt": "2026-06-23T10:00:00Z",
                    "source": {"name": "Reuters"},
                }
            ],
        }

        articles = main.load_newsapi_articles(payload)

        self.assertEqual(articles[0]["source_name"], "Reuters")
        self.assertEqual(articles[0]["link"], "https://example.com/a")


class AsyncWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_articles_skips_duplicates_and_non_forex_items(self):
        bot = AsyncMock()
        articles = [
            {"article_id": "1", "title": "Dollar rises on Fed optimism", "description": "USD gains", "link": "https://a", "pubDate": "2026-06-23T10:00:00Z"},
            {"article_id": "1", "title": "Dollar rises on Fed optimism", "description": "USD gains", "link": "https://a", "pubDate": "2026-06-23T10:00:00Z"},
            {"article_id": "2", "title": "Sports headline", "description": "Match report", "link": "https://b", "pubDate": "2026-06-23T10:00:00Z"},
        ]

        sent = await main.send_articles(bot, "@channel", articles, set())

        self.assertEqual(sent, 1)
        self.assertGreaterEqual(bot.send_message.await_count, 1)

    async def test_run_worker_cycle_fetches_and_sends(self):
        bot = AsyncMock()
        article = {"article_id": "1", "title": "Euro rises on ECB outlook", "description": "EUR gains", "link": "https://a", "pubDate": "2026-06-23T10:00:00Z"}

        with patch.object(main, "fetch_latest_articles", return_value=[article]):
            sent = await main.run_worker_cycle(bot, "@channel", set())

        self.assertEqual(sent, 1)
        self.assertGreaterEqual(bot.send_message.await_count, 1)



class MainTests(unittest.TestCase):
    def test_validate_config_lists_missing_variables_for_newsdata(self):
        with patch.object(main, "BOT_TOKEN", "PLACEHOLDER_TOKEN_REVOKED"), patch.object(main, "TELEGRAM_CHAT_ID", ""), patch.object(main, "NEWS_PROVIDER", "newsdata"), patch.object(main, "NEWSDATA_API_KEY", ""):
            missing = main.validate_config()

        self.assertEqual(missing, ["BOT_TOKEN", "TELEGRAM_CHAT_ID", "NEWSDATA_API_KEY"])

    def test_validate_config_lists_missing_variables_for_newsapi(self):
        with patch.object(main, "BOT_TOKEN", "token"), patch.object(main, "TELEGRAM_CHAT_ID", "@channel"), patch.object(main, "NEWS_PROVIDER", "newsapi"), patch.object(main, "NEWS_API_KEY", ""):
            missing = main.validate_config()

        self.assertEqual(missing, ["NEWS_API_KEY"])

    @patch.object(main, "worker_loop")
    def test_main_runs_worker_when_config_is_present(self, worker_loop_mock):
        with patch.object(main, "BOT_TOKEN", "token"), patch.object(main, "TELEGRAM_CHAT_ID", "@channel"), patch.object(main, "NEWS_PROVIDER", "newsapi"), patch.object(main, "NEWS_API_KEY", "demo"):
            with patch("main.asyncio.run") as run_mock:
                exit_code = main.main()

        self.assertEqual(exit_code, 0)
        run_mock.assert_called_once()
        coroutine_arg = run_mock.call_args.args[0]
        self.assertTrue(inspect.iscoroutine(coroutine_arg))
        coroutine_arg.close()

    def test_main_returns_error_when_config_missing(self):
        with patch.object(main, "BOT_TOKEN", "PLACEHOLDER_TOKEN_REVOKED"), patch.object(main, "TELEGRAM_CHAT_ID", ""), patch.object(main, "NEWS_PROVIDER", "newsapi"), patch.object(main, "NEWS_API_KEY", ""):
            self.assertEqual(main.main(), 1)


if __name__ == "__main__":
    unittest.main()
