#!/usr/bin/perl

$cpfid = $ARGV[0];

print qq[<!-- wp:heading {"level":4} -->
<h4 class="wp-block-heading">Contributions Map</h4>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p><a href="/candidate-data/contribution-maps/contributions_$cpfid.html" target="_blank" rel="noreferrer noopener">open map in new tab</a></p>
<!-- /wp:paragraph -->

<!-- wp:html -->
<iframe src="/candidate-data/contribution-maps/contributions_$cpfid.html" width="100%" height="600"></iframe>
<!-- /wp:html -->
];
