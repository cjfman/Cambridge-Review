#!/usr/bin/perl

use strict;
use warnings;
no warnings qw/uninitialized/;

use File::Basename;
use File::Spec::Functions 'catfile';
use Text::ParseWords;

my $max_replacements = 1000;
my @agenda_dirs = (
    catfile(dirname(__FILE__), "../meeting_data/processed"),
    catfile(dirname(__FILE__), "../processed"),
);
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

my %tooltip  = (
    ADA     => "American Disabilities Act",
    CPD     => "Cambridge Police Department",
    DCR     => "Department of Conservation and Recreation",
    EOPSS   => "Executive Office of Public Safety",
    MassDEP => "Massachusetts Department of Environmental Protection",
    MEMA    => "Massachusetts Emergency Management Agency",
);

## Get agenda item links
my %item_links;
foreach my $agenda_dir (@agenda_dirs) {
    %item_links = (%item_links, read_agenda_dir($agenda_dir));
}

## Process summary
my $replacements;
my $skip_replacements;
my $line_no;
foreach (<>) {
    $line_no++;
    ## Replace keyword fields
    while (/\{\{([^\}]+)\}\}/) {
        last if $skip_replacements;
        if ($replacements >= $max_replacements) {
            print STDERR "Reached maximum number of replacements $max_replacements on line $line_no\n";
            $skip_replacements = 1;
            last;
        }
        my ($name, $txt) = split /\|/, $1;
        $txt = $name unless defined $txt;
        $name =~ s/\s+/-/g;
        if ($name !~ /^[A-Z]+$/) {
            $name = lc $name;
        }
        if (defined $glossary{$name}) {
            print STDERR "Found glossary term with tooltip $name / $txt\n";
            s/(\{\{[^\}]+\}\})/[tooltips keyword='[$txt]($glossary_url#$name)' content='$glossary{$name}']/;
        }
        elsif (defined $tooltip{$txt}) {
            print STDERR "Found tooltip $name / $tooltip{$name}\n";
            s/(\{\{[^\}]+\}\})/[tooltips keyword='$txt' content='$tooltip{$txt}']/;
        }
        else {
            print STDERR "Found glossary term $name / $txt\n";
            s/(\{\{[^\}]+\}\})/[$txt]($glossary_url#$name)/;
        }
        $replacements++;
    }

    ## Insert agenda item links
    if (/\((\w+ \d+ #\d+)\)/) {
        last if $skip_replacements;
        if ($replacements >= $max_replacements) {
            print STDERR "Reached maximum number of replacements $max_replacements on line $line_no\n";
            $skip_replacements = 1;
            last;
        }
        my $uid = $1;
        s/$uid/[$uid]($item_links{$uid})/ if (defined $item_links{$uid});
        $replacements++;
    }
    print;
}

sub read_agenda_dir {
    my %item_links;
    my $agenda_dir = shift;
    if (-d $agenda_dir) {
        print STDERR "Opening directory '$agenda_dir'\n";
        opendir DIR, $agenda_dir;
        foreach my $name (readdir(DIR)) {
            next if $name =~ /^\./;
            my $agenda_path = "$agenda_dir/$name";
            if (-f $agenda_path) {
                %item_links = (%item_links, read_agenda_file($agenda_path));
            }
            elsif (-d $agenda_path) {
                %item_links = (%item_links, read_agenda_dir($agenda_path));
            }
        }
    }
    return %item_links;
}

sub read_agenda_file {
    my $path = shift;
    print STDERR "Opening '$path'\n";
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
