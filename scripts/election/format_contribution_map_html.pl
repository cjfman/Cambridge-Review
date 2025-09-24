#!/usr/bin/perl

$cpfid = $ARGV[0];

print qq[<!-- wp:heading {"level":4} -->
<h4 class="wp-block-heading">Contributions Map</h4>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p><a href="/candidate-data/contribution-maps/contributions_$cpfid.html" target="_blank" rel="noreferrer noopener">open map in new tab</a></p>
<!-- /wp:paragraph -->

<!-- wp:html -->
];

print qq[<div class="gbvc-hide-on-mobile">
<iframe src="/candidate-data/contribution-maps/contributions_$cpfid.html" width="100%" height="600"></iframe>
</div>
<div class="gbvc-hide-on-desktop gbvc-hide-on-tablet">
<iframe src="/candidate-data/contribution-maps/contributions_mobile_$cpfid.html" width="100%" height="600"></iframe>
</div>];

print qq[

<!-- /wp:html -->
];
