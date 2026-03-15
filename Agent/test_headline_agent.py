import unittest

from headline_agent import CNNHeadlineAgent


class CNNHeadlineAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = CNNHeadlineAgent()

    def test_extracts_five_headlines_from_article_links(self) -> None:
        html = """
        <html>
          <body>
            <a href="/2026/03/15/politics/story">
              Major policy fight expands across multiple states after overnight ruling
            </a>
            <a href="/2026/03/15/world/story">
              International monitors warn supply shortages could worsen before emergency aid arrives
            </a>
            <a href="/2026/03/15/health/story">
              Hospital systems prepare overflow plans as respiratory cases rise across several cities
            </a>
            <a href="/2026/03/15/business/story">
              Investors pull back from regional banks after regulators announce broader review measures
            </a>
            <a href="/2026/03/15/science/story">
              Researchers report unusually rapid ice loss after a month of record coastal temperatures
            </a>
            <a href="/2026/03/15/sport/story">
              Teams adjust travel plans after severe weather delays multiple tournament matchups
            </a>
          </body>
        </html>
        """

        headlines = self.agent.extract_headlines(html)

        self.assertEqual(len(headlines), 5)
        self.assertEqual(headlines[0], "Major policy fight expands across multiple states after overnight ruling")
        self.assertEqual(headlines[-1], "Researchers report unusually rapid ice loss after a month of record coastal temperatures")

    def test_extracts_headlines_from_json_ld(self) -> None:
        html = """
        <html>
          <head>
            <script type="application/ld+json">
              {
                "@context": "https://schema.org",
                "itemListElement": [
                  {
                    "@type": "NewsArticle",
                    "headline": "International markets react sharply as negotiators signal major tariff reversal"
                  },
                  {
                    "@type": "NewsArticle",
                    "headline": "Cabinet officials face growing pressure after audit reveals major budget gaps"
                  }
                ]
              }
            </script>
          </head>
        </html>
        """

        headlines = self.agent.extract_headlines(html)

        self.assertEqual(
            headlines,
            [
                "International markets react sharply as negotiators signal major tariff reversal",
                "Cabinet officials face growing pressure after audit reveals major budget gaps",
            ],
        )

    def test_extracts_headlines_from_h1_fallback(self) -> None:
        html = """
        <html>
          <body>
            <h1>
              Emergency crews race to restore service after severe storm disrupts regional transit
            </h1>
            <h1>
              Negotiators return to talks as ceasefire proposal gains support from regional allies
            </h1>
          </body>
        </html>
        """

        headlines = self.agent.extract_headlines(html)

        self.assertEqual(
            headlines,
            [
                "Emergency crews race to restore service after severe storm disrupts regional transit",
                "Negotiators return to talks as ceasefire proposal gains support from regional allies",
            ],
        )

    def test_extracts_headline_from_og_title_fallback(self) -> None:
        html = """
        <html>
          <head>
            <meta property="og:title" content="Senators scramble for votes as budget talks enter critical weekend">
          </head>
        </html>
        """

        headlines = self.agent.extract_headlines(html)

        self.assertEqual(
            headlines,
            ["Senators scramble for votes as budget talks enter critical weekend"],
        )

    def test_deduplicates_repeated_headlines(self) -> None:
        html = """
        <html>
          <body>
            <a href="/2026/03/15/politics/story">
              Major policy fight expands across multiple states after overnight ruling
            </a>
            <h1>
              Major policy fight expands across multiple states after overnight ruling
            </h1>
          </body>
        </html>
        """

        headlines = self.agent.extract_headlines(html)

        self.assertEqual(
            headlines,
            ["Major policy fight expands across multiple states after overnight ruling"],
        )

    def test_raises_when_no_story_headline_exists(self) -> None:
        html = """
        <html>
          <body>
            <h1>Breaking News, Latest News and Videos | CNN</h1>
            <a href="/live-news">Watch Live</a>
          </body>
        </html>
        """

        with self.assertRaises(ValueError):
            self.agent.extract_headlines(html)


if __name__ == "__main__":
    unittest.main()
