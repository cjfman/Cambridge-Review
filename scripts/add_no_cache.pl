#!/usr/bin/perl

use strict;
use warnings;
no warnings qw/uninitialized/;

my $no_cache = '<head>
    <meta charset="utf-8" />
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
    <meta http-equiv="Pragma" content="no-cache" />
    <meta http-equiv="Expires" content="0" />
</head>';

my $file = shift @ARGV;
my $found;
my @lines;
open FILE, '<', $file or die "Failed to open file $file: $!";
foreach my $line (<FILE>) {
    chomp $line;
    if ($line eq '<head><meta charset="utf-8" /></head>') {
        push @lines, $no_cache;
        $found = 1;
    }
    else {
        push @lines, $line;
    }
}
close FILE;
if (!$found) {
    print STDERR "File $file not updated\n";
    exit;
}
open FILE, '>', $file or die "Failed to open file $file: $!";
print FILE join "\n", @lines;
close FILE;
print STDERR "File $file updated\n";
