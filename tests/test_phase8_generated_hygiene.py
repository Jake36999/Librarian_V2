from resource_librarian.structure import _files
from resource_librarian.content_roots import _walk


def test_native_survey_and_content_walk_exclude_generated_bundles(tmp_path):
    for rel in ['src/resource_librarian/ui/app.js', 'ui/src/app.ts', 'dist/bundle.js']:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('export const value = 1;', encoding='utf-8')
    assert 'src/resource_librarian/ui/app.js' not in _files(tmp_path)
    assert 'ui/src/app.ts' in _files(tmp_path)
    assert 'src/resource_librarian/ui/app.js' not in {
        p.relative_to(tmp_path).as_posix() for p in _walk(tmp_path, markdown_only=False)}
