from tablefind.spot_check import draw


def test_draw_takes_up_to_the_target_per_size_and_is_seeded():
    key = {f"q{i}": {f"t{j}" for j in range(1 + i % 4)} for i in range(40)}
    picked = draw(key)
    sizes = [len(key[q]) for q in picked]
    assert sum(s == 1 for s in sizes) == 7 and sum(s == 2 for s in sizes) == 7 and sum(s >= 3 for s in sizes) == 6
    assert picked == draw(dict(reversed(list(key.items()))))
