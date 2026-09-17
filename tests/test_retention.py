from tone_builder.retention import decide, split


def test_split_alternates_in_time_order():
    assert split(8) == ([0, 2, 4, 6], [1, 3, 5, 7])


def test_overfit_eq_is_rejected():
    fit, test = split(8)
    base = [8.0] * 8
    eq = [5.0 if i in fit else 12.0 for i in range(8)]
    r = decide(base, {"eq": eq}, fit, test)
    assert r["best"] == "eq"
    assert r["accepted"] is False


def test_consistent_improvement_is_accepted():
    fit, test = split(8)
    base = [8.0, 8.1, 7.9, 8.0, 8.1, 7.9, 8.0, 8.1]
    better = [v - 1.0 for v in base]
    better[3] += 0.1
    r = decide(base, {"x": better}, fit, test)
    assert r["accepted"] is True
    assert abs(r["improvement_db"] - 0.975) < 1e-9


def test_improvement_inside_the_noise_is_rejected():
    fit, test = split(8)
    base = [8.0] * 8
    cand = [7.0] * 8
    for i, d in zip(test, [2.0, -1.5, 1.8, -1.9]):
        cand[i] = 8.0 - d
    r = decide(base, {"x": cand}, fit, test)
    assert r["accepted"] is False
    assert r["noise_db"] > r["improvement_db"]


def test_best_is_ranked_on_fit_notes_only():
    fit, test = split(4)
    r = decide([9.0] * 4, {"a": [6, 1, 6, 1], "b": [5, 9, 5, 9]}, fit, test)
    assert r["best"] == "b"
