import json

from pokedb.output import publish_staged_output, write_index_file
from pokedb.utils.file_ops import write_json_file


def test_partial_index_update_preserves_unrequested_resources(tmp_path):
    existing_index = {
        "metadata": {"generation": 9},
        "ability": [{"id": 1, "name": "stench"}],
        "move": [{"id": 1, "name": "pound"}],
    }

    write_index_file(
        {"move": [{"id": 2, "name": "karate-chop"}]},
        target_gen=9,
        output_dir=tmp_path,
        generation_version_groups={9: ["scarlet-violet"]},
        existing_index=existing_index,
        replaced_keys={"move"},
    )

    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert index["ability"] == existing_index["ability"]
    assert index["move"] == [{"id": 2, "name": "karate-chop"}]
    assert index["metadata"]["counts"] == {"ability": 1, "move": 1}


def test_publish_staged_output_replaces_complete_tree(tmp_path):
    final_output = tmp_path / "gen9"
    final_output.mkdir()
    (final_output / "old.json").write_text("{}", encoding="utf-8")
    staging_output = tmp_path / ".gen9.staging"
    staging_output.mkdir()
    (staging_output / "new.json").write_text("{}", encoding="utf-8")

    publish_staged_output(staging_output, final_output)

    assert not (final_output / "old.json").exists()
    assert (final_output / "new.json").exists()


def test_resource_writer_preserves_canonical_identifier_keys(tmp_path):
    write_json_file(
        tmp_path,
        "example",
        {"effect": {"scarlet-violet": "text"}, "stats": {"special-attack": 100}},
    )

    data = json.loads((tmp_path / "example.json").read_text(encoding="utf-8"))
    assert set(data["effect"]) == {"scarlet-violet"}
    assert set(data["stats"]) == {"special-attack"}
