#!/usr/bin/env python3

import argparse
import sys

from pathlib import Path

SCRIPT = r"""<script>
(function() {
    var div = document.querySelector('.plotly-graph-div');
    if (!div) return;

    var shiftObserver = null;

    function applyShift(g) {
        var t = g.getAttribute('transform') || '';
        if (/ translate\([^,]+,0\)$/.test(t)) return;
        var bbox = g.getBBox();
        if (bbox.x >= 0) return;
        g.setAttribute('transform', t + ' translate(' + (-bbox.x) + ',0)');
    }

    div.on('plotly_hover', function(data) {
        if (shiftObserver) { shiftObserver.disconnect(); shiftObserver = null; }

        setTimeout(function() {
            var g = div.querySelector('g.hovertext');
            if (!g) return;

            var transform = g.getAttribute('transform') || '';
            var match = transform.match(/translate\(([^,]+),/);
            if (!match) return;
            var tx = parseFloat(match[1]);

            var svg = div.querySelector('svg.main-svg');
            if (!svg || tx < parseFloat(svg.getAttribute('width')) / 2) return;

            applyShift(g);

            shiftObserver = new MutationObserver(function(mutations) {
                mutations.forEach(function(m) {
                    if (m.attributeName === 'transform') applyShift(m.target);
                });
            });
            shiftObserver.observe(g, { attributes: true, attributeFilter: ['transform'] });
        }, 10);
    });

    div.on('plotly_unhover', function() {
        if (shiftObserver) { shiftObserver.disconnect(); shiftObserver = null; }
    });
})();
</script>
"""


def insertTooltipAdjustment(path) -> bool:
    with open(path, 'r', encoding='utf8') as f:
        content = f.read()

    if 'applyShift' in content:
        return False

    idx = content.rfind('</body>')
    if idx < 0:
        return False

    content = content[:idx] + SCRIPT + content[idx:]
    with open(path, 'w', encoding='utf8') as f:
        f.write(content)

    return True


def make_parser():
    parser = argparse.ArgumentParser(
        description="Inject right-side tooltip adjustment into a Plotly HTML file")
    parser.add_argument("html_file", help="HTML file to modify")
    return parser


def main() -> int:
    args = make_parser().parse_args()
    if insertTooltipAdjustment(args.html_file):
        print(f"Inserted tooltip adjustment into '{args.html_file}'")
    else:
        print(f"No </body> tag found (or already applied) in '{args.html_file}'", file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
