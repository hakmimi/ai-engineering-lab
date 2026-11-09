import pytest

from shared.publish_post import publish, readme_to_post

REPO = "https://github.com/hakmimi/ai-engineering-lab"
README = """# 07 · Does X really work?

## How this started

So, I came across [this article](https://example.com/a). See [`data/NOTICE.md`](data/NOTICE.md),
the [helper](../../shared/llm.py), the [design folder](design/) and [results](#the-results).

![The flow](design/process-diagram.png)

![Caught](charts/caught.svg)

```
not a link: [x](data/y.json)
```

### Lessons from building it

Lesson.

<details>
<summary><b>The folder and how to run it</b></summary>

```
07-x/
```

</details>
"""

KW = dict(slug="07-x", title='Does "X" work?', description="Short.", pub="2026-11-12T10:00:00+02:00",
          tags=["evals", "agents"], topic_dir="topics/07-x-thing")


def test_frontmatter_and_h1_removed():
    post, _ = readme_to_post(README, **KW)
    head = post.split("---")[1]
    assert 'title: "Does \\"X\\" work?"' in head
    assert "pubDatetime: 2026-11-12T10:00:00+02:00" in head
    assert 'tags: ["evals", "agents"]' in head
    assert "draft: false" in head
    assert "# 07 ·" not in post
    assert post.split("---", 2)[2].lstrip().startswith("## How this started")


def test_images_point_to_blog_assets_and_are_listed():
    post, images = readme_to_post(README, **KW)
    assert "![The flow](../../assets/images/07-x/process-diagram.png)" in post
    assert "![Caught](../../assets/images/07-x/caught.svg)" in post
    assert images == ["design/process-diagram.png", "charts/caught.svg"]


def test_relative_links_become_github_links_on_main():
    post, _ = readme_to_post(README, **KW)
    assert f"[`data/NOTICE.md`]({REPO}/blob/main/topics/07-x-thing/data/NOTICE.md)" in post
    assert f"[helper]({REPO}/blob/main/shared/llm.py)" in post
    assert f"[design folder]({REPO}/tree/main/topics/07-x-thing/design)" in post
    assert "[this article](https://example.com/a)" in post
    assert "[results](#the-results)" in post


def test_code_blocks_left_alone():
    post, _ = readme_to_post(README, **KW)
    assert "not a link: [x](data/y.json)" in post


def test_details_box_becomes_the_code_link():
    post, _ = readme_to_post(README, **KW, code_blurb="It has the tests and the runs.")
    assert "<details>" not in post and "07-x/\n" not in post
    assert (f"### The code\n\nEverything is on GitHub: [ai-engineering-lab / 07-x-thing]"
            f"({REPO}/tree/main/topics/07-x-thing). It has the tests and the runs.") in post


def test_two_images_with_the_same_name_is_an_error():
    text = "# T\n\n![a](design/a.png)\n\n![b](charts/a.png)\n"
    with pytest.raises(ValueError, match="a.png"):
        readme_to_post(text, **KW)


def _topic(tmp_path):
    topic = tmp_path / "lab" / "topics" / "07-x-thing"
    (topic / "design").mkdir(parents=True)
    (topic / "charts").mkdir()
    (topic / "README.md").write_text(README, encoding="utf-8")
    (topic / "design" / "process-diagram.png").write_bytes(b"png")
    (topic / "charts" / "caught.svg").write_text("<svg/>", encoding="utf-8")
    return topic


def test_publish_writes_post_and_copies_images(tmp_path):
    topic, blog = _topic(tmp_path), tmp_path / "Blog"
    post_path = publish(topic, blog, **{k: v for k, v in KW.items() if k != "topic_dir"})
    assert post_path == blog / "src" / "content" / "posts" / "07-x.md"
    assert "## How this started" in post_path.read_text(encoding="utf-8")
    assets = blog / "src" / "assets" / "images" / "07-x"
    assert (assets / "process-diagram.png").read_bytes() == b"png"
    assert (assets / "caught.svg").exists()


def test_publish_refuses_to_overwrite_unless_forced(tmp_path):
    topic, blog = _topic(tmp_path), tmp_path / "Blog"
    kw = {k: v for k, v in KW.items() if k != "topic_dir"}
    publish(topic, blog, **kw)
    with pytest.raises(FileExistsError):
        publish(topic, blog, **kw)
    publish(topic, blog, **kw, force=True)


def test_publish_fails_on_missing_image(tmp_path):
    topic, blog = _topic(tmp_path), tmp_path / "Blog"
    (topic / "charts" / "caught.svg").unlink()
    with pytest.raises(FileNotFoundError, match="caught.svg"):
        publish(topic, blog, **{k: v for k, v in KW.items() if k != "topic_dir"})
    assert not (blog / "src" / "content" / "posts" / "07-x.md").exists()


def test_source_logos_field_only_when_given():
    post, _ = readme_to_post(README, **KW, sources=["linkedin", "pinterest"])
    assert 'source: ["linkedin", "pinterest"]' in post.split("---")[1]
    plain, _ = readme_to_post(README, **KW)
    assert "source:" not in plain.split("---")[1]
