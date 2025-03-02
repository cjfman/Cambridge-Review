#!/usr/bin/perl

use strict;
use warnings;
no warnings qw/uninitialized/;

use File::Basename;
use File::Spec::Functions 'catfile';
use Text::ParseWords;

my $agenda_dir = catfile(dirname(__FILE__), "../meeting_data/processed/current");
my $glossary_url = '/the-city/city-glossary';
my $lines;
my %glossary = (
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

my %tooltip = (
    DCR  => "Department of Conservation and Recreation",
);

## Get agenda item links
my %item_links;
if (-d $agenda_dir) {
    print STDERR "Opening directory '$agenda_dir'\n";
    opendir DIR, $agenda_dir;
    foreach my $name (readdir(DIR)) {
        my $agenda_item_path = "$agenda_dir/$name";
        next unless -f $agenda_item_path;
        print STDERR "Opening '$agenda_item_path'\n";
        %item_links = (%item_links, read_agenda_items($agenda_item_path));
    }
}

## Process summary
foreach (<>) {
    ## Replace keyword fields
    while (/\{\{([^\}]+)\}\}/) {
        my ($name, $txt) = split /\|/, $1;
        $txt = $name unless defined $txt;
        $name =~ s/\s+/-/g;
        if ($name !~ /^[A-Z]+$/) {
            $name = lc $name;
        }
        if (defined $glossary{$name}) {
            s/(\{\{[^\}]+\}\})/[tooltips keyword='[$txt]($glossary_url#$name)' content='$glossary{$name}']/;
        }
        elsif (defined $tooltip{$name}) {
            s/(\{\{[^\}]+\}\})/[tooltips keyword='$txt' content='$tooltip{$name}']/;
        }
        else {
            s/(\{\{[^\}]+\}\})/[$txt]($glossary_url#$name)/;
        }
    }

    ## Insert agenda item links
    while (/\((\w+ \d+ #\d+)\)/) {
        my $uid = $1;
        s/$uid/[$uid]($item_links{$uid})/ if (defined $item_links{$uid});
    }
    print;
}

sub read_agenda_items {
    my $path = shift;
    my %item_links;
    open FILE, '<', $path or return ();
    my $first = 1;
    my %headers;
    foreach my $line (<FILE>) {
        my @fields = Text::ParseWords::parse_line(',', 0, $line);
        if ($first) {
            %headers = map { $fields[$_] => $_ } (0..$#fields);
            $first = 0;
            next;
        }
        $item_links{$fields[$headers{'Unique Identifier'}]} = $fields[$headers{Link}];
    }
    return %item_links;
}
