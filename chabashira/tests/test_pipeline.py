"""APIに接続せずに、解析・集計・本文生成を確かめる。

サンプルXMLの要素名は仕様書からの想定。実際の応答と違えば
kkj.FIELD_CANDIDATES を直し、このサンプルも実物に合わせて差し替える。
"""

from datetime import date

from chabashira import digest, kkj, survey

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Results>
  <Version>1.0</Version>
  <SearchResults>
    <SearchHits>3</SearchHits>
    <SearchResult>
      <Key>A1</Key>
      <ExternalDocumentURI>https://example.lg.jp/a1</ExternalDocumentURI>
      <ProjectName>市役所本庁舎日常清掃業務委託</ProjectName>
      <OrganizationName>大阪府○○市</OrganizationName>
      <PrefectureName>大阪府</PrefectureName>
      <CityName>○○市</CityName>
      <CftIssueDate>2026-10-05</CftIssueDate>
      <TenderSubmissionDeadline>2026-10-20</TenderSubmissionDeadline>
      <Category>役務</Category>
    </SearchResult>
    <SearchResult>
      <Key>A2</Key>
      <ExternalDocumentURI>https://example.lg.jp/a2</ExternalDocumentURI>
      <ProjectName>小学校卒業記念品の購入</ProjectName>
      <OrganizationName>大阪府△△市</OrganizationName>
      <CftIssueDate>2026-10-06</CftIssueDate>
    </SearchResult>
    <SearchResult>
      <Key>A3</Key>
      <ExternalDocumentURI>https://example.lg.jp/a3</ExternalDocumentURI>
      <ProjectName>図書館トイレ清掃業務</ProjectName>
      <OrganizationName>大阪府□□町</OrganizationName>
      <CftIssueDate>2026-06-01</CftIssueDate>
    </SearchResult>
  </SearchResults>
</Results>"""


def fake_search(query, **kwargs):
    hits, notices = kkj.parse_results(SAMPLE_XML)
    start, end = kwargs.get("issued_from"), kwargs.get("issued_to")
    notices = [n for n in notices if n.issued_date and start <= n.issued_date <= end]
    return hits, notices


def no_pause():
    pass


def test_parse_results_reads_fields():
    hits, notices = kkj.parse_results(SAMPLE_XML)
    assert hits == 3
    assert len(notices) == 3
    first = notices[0]
    assert first.key == "A1"
    assert first.get("title") == "市役所本庁舎日常清掃業務委託"
    assert first.get("organization") == "大阪府○○市"
    assert first.issued_date == date(2026, 10, 5)


def test_collect_excludes_artec_fields_and_dedupes():
    found = survey.collect("清掃", "大阪府", date(2026, 10, 1), date(2026, 10, 8), fake_search, no_pause)
    # A2（記念品）は除外、A3は期間外、A1はキーワードが複数当たっても1件
    assert list(found) == ["A1"]


def test_survey_counts_per_week():
    rows = survey.run(["大阪府"], days=7, today=date(2026, 10, 8), search=fake_search, pause=no_pause)
    cleaning = next(r for r in rows if r["業種"] == "清掃")
    assert cleaning["案件数"] == 1
    assert cleaning["週あたり"] == 1.0
    assert "| 清掃 | 大阪府 | 1 |" in survey.to_markdown(rows)


def test_digest_renders_with_source_and_unsubscribe():
    def fake_summarizer(notice):
        return digest.Summary(notice, "庁舎の日常清掃（1年間）", "大阪府○○市の入札参加資格（清掃）",
                              "公告に記載なし", "2026-10-20 17:00", "")

    text, page, count = digest.build("清掃", ["大阪府"], days=7, today=date(2026, 10, 8),
                                     search=fake_search, pause=no_pause, summarizer=fake_summarizer)
    assert count == 1
    assert "市役所本庁舎日常清掃業務委託" in text
    assert "https://example.lg.jp/a1" in text
    assert "官公需情報ポータルサイト" in text
    assert "配信停止" in page
    assert "<script" not in page
