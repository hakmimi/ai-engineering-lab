"""Turn a topic README into a blog post for the Astro blog (C:\\Workshop\\Blog) and copy its images.

    python -m shared.publish_post topics/05-x --blog ../Blog --slug 05-x \\
        --title "Does X work?" --description "One or two sentences." \\
        --date 2026-11-12T10:00:00+02:00 --tags evals,agents --code-blurb "It has ..."

What changes: the H1 goes (the frontmatter title replaces it); images point to
src/assets/images/<slug>/; relative links become GitHub links on main; the collapsed
<details> folder box becomes a short "### The code" link. Code blocks are left as they are.
A post with a future date stays hidden until that day (the blog rebuilds daily).
"""

from __future__ import annotations

import argparse
import datetime
import json
import posixpath
import re
import shutil
import sys
from pathlib import Path

REPO_URL = "https://github.com/hakmimi/ai-engineering-lab"
_LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)\)")
_DETAILS = re.compile(r"<details>.*?</details>\n?", re.S)
_FENCE = re.compile(r"^```.*?^```[^\n]*\n?", re.S | re.M)


def _is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "#", "mailto:"))


def _github(target: str, topic_dir: str, repo_url: str) -> str:
    path, _, anchor = target.partition("#")
    is_dir = path.endswith("/") or "." not in posixpath.basename(path.rstrip("/"))
    full = posixpath.normpath(posixpath.join(topic_dir, path))
    url = f"{repo_url}/{'tree' if is_dir else 'blob'}/main/{full}"
    return url + (f"#{anchor}" if anchor else "")


def readme_to_post(readme: str, *, slug: str, title: str, description: str, pub: str, tags: list[str],
                   topic_dir: str, repo_url: str = REPO_URL, code_blurb: str = "",
                   sources: list[str] | None = None,
                   articles: list[tuple[str, str, str, str]] | None = None) -> tuple[str, list[str]]:
    """Return (post text, image paths relative to the topic folder, in order of first use)."""
    body = re.sub(r"\A\s*# [^\n]*\n+", "", readme)
    code_url = f"{repo_url}/tree/main/{topic_dir}"
    code = f"### The code\n\nEverything is on GitHub: [ai-engineering-lab / {posixpath.basename(topic_dir)}]({code_url})."
    body = _DETAILS.sub((code + (f" {code_blurb}" if code_blurb else "") + "\n").replace("\\", "\\\\"), body)

    images: list[str] = []
    names: dict[str, str] = {}

    def fix(m: re.Match) -> str:
        bang, text, target = m.groups()
        if _is_external(target):
            return m.group(0)
        if bang:
            name = posixpath.basename(target)
            if names.get(name, target) != target:
                raise ValueError(f"two images share the name {name}: {names[name]} and {target}")
            if name not in names:
                names[name] = target
                images.append(target)
            return f"![{text}](../../assets/images/{slug}/{name})"
        return f"[{text}]({_github(target, topic_dir, repo_url)})"

    parts, last = [], 0
    for fence in _FENCE.finditer(body):  # rewrite only outside code blocks
        parts.append(_LINK.sub(fix, body[last:fence.start()]))
        parts.append(fence.group(0))
        last = fence.end()
    parts.append(_LINK.sub(fix, body[last:]))

    front = "\n".join([
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"description: {json.dumps(description, ensure_ascii=False)}",
        f"pubDatetime: {pub}",
        f"tags: {json.dumps(tags, ensure_ascii=False)}",
        *([f"source: {json.dumps(sources, ensure_ascii=False)}"] if sources else []),
        *(["articles:"] + [_article_yaml(*a) for a in articles] if articles else []),
        "draft: false",
        "---",
        "",
    ])
    return front + "\n" + "".join(parts).rstrip() + "\n", images


def _article_yaml(publisher: str, title: str, url: str, day: str) -> str:
    q = lambda s: json.dumps(s, ensure_ascii=False)  # noqa: E731
    return "\n".join([f"  - publisher: {q(publisher)}", f"    title: {q(title)}", f"    url: {q(url)}", f"    date: {day}"])


def publish(topic: Path, blog: Path, *, slug: str, title: str, description: str, pub: str, tags: list[str],
            code_blurb: str = "", force: bool = False, repo_url: str = REPO_URL, sources: list[str] | None = None,
            articles: list[tuple[str, str, str, str]] | None = None) -> Path:
    """Write <blog>/src/content/posts/<slug>.md and copy the images. Checks everything before writing."""
    post, images = readme_to_post((topic / "README.md").read_text(encoding="utf-8"), slug=slug, title=title,
                                  description=description, pub=pub, tags=tags, topic_dir=f"topics/{topic.name}",
                                  repo_url=repo_url, code_blurb=code_blurb, sources=sources, articles=articles)
    post_path = blog / "src" / "content" / "posts" / f"{slug}.md"
    if post_path.exists() and not force:
        raise FileExistsError(f"{post_path} exists; pass force=True (--force) to replace it")
    missing = [i for i in images if not (topic / i).is_file()]
    if missing:
        raise FileNotFoundError(f"images missing in {topic}: {', '.join(missing)}")
    assets = blog / "src" / "assets" / "images" / slug
    assets.mkdir(parents=True, exist_ok=True)
    for i in images:
        shutil.copyfile(topic / i, assets / posixpath.basename(i))
    post_path.parent.mkdir(parents=True, exist_ok=True)
    post_path.write_text(post, encoding="utf-8")
    return post_path


def parse_article(arg: str) -> tuple[str, str, str, str]:
    """ "Publisher|Title|URL|YYYY-MM-DD" → a tuple; the date is when the article came out (shown on the post and the Timeline)."""
    parts = [x.strip() for x in arg.split("|")]
    if len(parts) != 4:
        raise ValueError(f"--article needs Publisher|Title|URL|YYYY-MM-DD, got {arg!r}")
    publisher, title, url, day = parts
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"--article URL must start with http(s)://, got {url!r}")
    try:
        datetime.date.fromisoformat(day)
    except ValueError:
        raise ValueError(f"--article date must be YYYY-MM-DD, got {day!r}") from None
    if len(day) != 10:
        raise ValueError(f"--article date must be YYYY-MM-DD, got {day!r}")
    return publisher, title, url, day


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Publish a topic README as a blog post.")
    p.add_argument("topic", type=Path, help="the topic folder, e.g. topics/05-x")
    p.add_argument("--blog", type=Path, default=Path(r"C:\Workshop\Blog"))
    p.add_argument("--slug", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--date", required=True, help="pubDatetime with offset, e.g. 2026-11-12T10:00:00+02:00")
    p.add_argument("--tags", required=True, help="comma separated")
    p.add_argument("--code-blurb", default="")
    p.add_argument("--source", default="", help="logo keys from the blog's src/utils/sources.ts, comma separated (e.g. linkedin,pinterest)")
    p.add_argument("--article", action="append", default=[], type=parse_article,
                   help='the article the post tests, "Publisher|Title|URL|YYYY-MM-DD"; repeat for more than one')
    p.add_argument("--force", action="store_true")
    a = p.parse_args(argv)
    path = publish(a.topic.resolve(), a.blog, slug=a.slug, title=a.title, description=a.description, pub=a.date,
                   tags=[t.strip() for t in a.tags.split(",") if t.strip()], code_blurb=a.code_blurb, force=a.force,
                   sources=[s.strip() for s in a.source.split(",") if s.strip()] or None, articles=a.article or None)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
