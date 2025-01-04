#!/usr/bin/perl

use strict;
use warnings;
no warnings qw/uninitialized/;

my $glossary_url = '/the-city/city-glossary';
my $lines;
foreach (<>) {
	while (/\{\{([^\}]+)\}\}/) {
		my ($name, $txt) = split /\|/, $1;
		$txt = (defined $txt) ? $txt : $name;
		$name =~ s/\s+/-/g;
        if ($name !~ /^[A-Z]+$/) {
            $name = lc $name;
        }
		s/(\{\{[^\}]+\}\})/[$txt]($glossary_url#$name)/;
	}
	print;
}
