#!/usr/bin/perl

use strict;
use warnings;
no warnings qw/uninitialized/;

use Text::ParseWords;

my $exit_on_error;

if (@ARGV != 2) {
    print "USAGE: $0 <session year> <meetings file>\n";
    exit 1;
}

my $header = 0;
my $year = shift @ARGV;
my $path = shift @ARGV;
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
    #next if -f $jsn;
    if (! -f $pdf) {
        print "Saving '$actions' to $pdf\n";
        system "curl '$actions' > $pdf";
    }
    else {
        print "Found $pdf cached";
    }
    if (! -f $txt) {
        system 'pdftotext', $pdf, $txt;
        system './scripts/prep_final_actions.pl', $txt;
    }
    my $cmd = "./scripts/tabulate_votes.py --councillor-info meeting_data/councilors.yml --session $year $txt > $jsn";
    print "$cmd\n";
    my $code = system $cmd;
    if ($code != 0 && $exit_on_error) {
        exit $code;
    }
    if (! -s $jsn) {
        unlink $jsn;
    }
}
