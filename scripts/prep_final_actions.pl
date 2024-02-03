#!/usr/bin/perl

use strict;
use warnings;
no warnings qw/uninitialized/;

my @headers = map "$_:", qw/RESULT YEAS NAYS PRESENT/;

my $path = $ARGV[0];
my $lastline;
open IN_FILE,  '<', $path       or die "Failed to open '$path': $!";
open OUT_FILE, '>', "$path.tmp" or die "Failed to open '$path.tmp': $!";
foreach my $line (<IN_FILE>) {
    chomp $line;
    last if $line =~ /COMMITTEE REPORTS/;
    next if $line eq 'CITY OF CAMBRIDGE';
    next if $line eq "" and (grep { $lastline eq $_ } @headers);
    print OUT_FILE "$line\n";
    $lastline = $line;
}
close IN_FILE;
close OUT_FILE;
rename "$path.tmp", $path
