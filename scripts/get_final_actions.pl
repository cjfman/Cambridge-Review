#!/usr/bin/perl

use strict;
use warnings;
no warnings qw/uninitialized/;

use Text::ParseWords;

my $header = 0;
my $path = $ARGV[0];
open FILE, '<', $path or die "Failed to open '$path': $!";
foreach (<FILE>) {
    if (!$header) {
        $header = 1;
        next;
    }
    chomp;
    my ($body, $type, $other, $date, $time, $status, $id, $url, $summary, $packet, $actions) = Text::ParseWords::parse_line(',', 0, $_);;
    next if $actions eq "";
    my $pdf = "meeting_data/cache/final_actions_meeting_$id.pdf";
    my $txt = "meeting_data/cache/final_actions_meeting_$id.txt";
    my $jsn = "meeting_data/cache/final_actions_meeting_$id.json";
    next if -f $jsn;
    if (! -f $pdf) {
        print "Saving '$actions' to $pdf\n";
        system "curl '$actions' > $pdf";
    }
    if (! -f $txt) {
        system 'pdftotext', $pdf, $txt;
        system './scripts/prep_final_actions.pl', $txt;
    }
    system "./scripts/tabulate_votes.py $txt > $jsn";
}
