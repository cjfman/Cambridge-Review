#!/usr/bin/perl

use strict;
use warnings;
no warnings qw/uninitialized/;

my $glossary_url = '/the-city/city-glossary';
my $lines;
my %glossary  = (
    AHO  => "Affordable Housing Overlay",
    BZA  => "Board of Zoning Appeals",
    CDD  => "Community Development Department",
    CHA  => "Cambridge Housing Authority",
    CSO  => "Cycling Safety Ordinance",
    DPW  => "Department of Public Works",
    PACE => "Property Assessment Clean Energy Massachusetts",
    RFP  => "Request for Proposal",
    STIR => "Surveillance Technology Impact Report",
    STO  => "Surveillance Technology Ordinance",
);

foreach (<>) {
    while (/\{\{([^\}]+)\}\}/) {
        my ($name, $txt) = split /\|/, $1;
        $txt = (defined $txt) ? $txt : $name;
        $name =~ s/\s+/-/g;
        if ($name !~ /^[A-Z]+$/) {
            $name = lc $name;
        }
        if (defined $glossary{$name}) {
            s/(\{\{[^\}]+\}\})/[tooltips keyword='[$txt]($glossary_url#$name)' content='$glossary{$name}']/;
        }
        else {
            s/(\{\{[^\}]+\}\})/[$txt]($glossary_url#$name)/;
        }
    }
    print;
}
