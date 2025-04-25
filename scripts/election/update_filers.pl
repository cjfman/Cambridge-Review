#!/usr/bin/perl

use strict;
use warnings;
no warnings qw/uninitialized/;

use File::Compare;
use File::Copy;

my $base_dir = ".";
$base_dir = shift @ARGV if @ARGV;
$base_dir =~ s{/$}{};

my $scripts_dir  = "$base_dir/scripts";
my $filers_file  = "$base_dir/candidate_data/filers.json";
my $reports_path = "$base_dir/candidate_data/reports";
my $charts_path  = "$base_dir/charts/filers/reports";

$reports_path =~ s{/$}{};
$charts_path  =~ s{/$}{};

print STDERR "Checking for filers\n";
my @cpfids = `$scripts_dir/election/ocpf.py list-filers --reports $reports_path --missing-recent-report`;
chomp @cpfids;
@cpfids = grep $_, @cpfids;

my $num = @cpfids;
my @charts;
my $errors;
print STDERR "Found $num filers\n";
foreach my $cpfid (@cpfids) {
    ## Get report
    my $tmp = "/tmp/${cpfid}_reports.json";
    my $report_file = "$reports_path/${cpfid}_reports.json";
    my $chart_file = "$charts_path/${cpfid}_report_chart.html";
    my $updated;
    if (-f $report_file and -M $report_file < 1) {
        print STDERR "Report file '$report_file' was written or checked today. Don't check for update\n";
    }
    else {
        print STDERR "Getting reports for filer $cpfid and saving them to $report_file\n";
        system "$scripts_dir/election/ocpf.py query-reports $cpfid $tmp 1>&2";
        if ($?) {
            print STDERR "Failed to query report for filer $cpfid: $?";
            $errors++;
        }
        elsif (-f $report_file and compare($tmp, $report_file) != 1) {
            print STDERR "No report update for filer $cpfid\n";
            system 'touch', $report_file;
        }
        else {
            ## Put report in place
            if (!move($tmp, $report_file)) {
                print STDERR "Failed to save file to '$report_file'\n";
                $errors++;
            }
            else {
                $updated = 1;
            }
        }
    }

    ## Make a chart from the report
    if (-f $report_file and (not -f $chart_file or $updated)) {
        print "Report update for filer $cpfid saved in $report_file. Making chart and saving to '$chart_file'\n";
        system "$scripts_dir/election/plot_finances.py single-filer --out '$chart_file' --in-file '$report_file' --copyright-tight --h-legend 1>&2";
        if ($?) {
            $errors++;
            print STDERR "Failed to make chart file '$chart_file': $?\n";
        }
        else {
            system "$scripts_dir/add_no_cache.pl $chart_file";
            push @charts, $chart_file;
        }

        if (! -f $chart_file) {
            print "Making empty report chart for filer $cpfid\n";
            copy("$charts_path/empty_report_chart.html", $chart_file);
            push @charts, $chart_file;
        }
    }
    elsif (-f $chart_file) {
        print STDERR "Not updating chart file $chart_file\n";
    }
    elsif (not -f $report_file) {
        print STDERR "Cannot make a chart file '$chart_file' as the report file '$report_file' is missing\n";
    }
    unlink $tmp if -f $tmp;
}

$num = @charts;
print STDERR "Made $num new chart(s)\n";
if (@charts) {
    print "Moving $num charts to server\n";
    system '/bin/bash', '-c', "sftp -P19199 -i $ENV{HOME}/.ssh/charles_server_cx franklin\@franklin.cx:public_html/candidate-data/report-charts <<< \$'put $_'" foreach @charts;
    if ($?) {
        print STDERR "Failed to upload charts to server: $?\n";
        $errors++;
    }
}

exit ($errors) ? 1 : 0;
