#!/usr/bin/perl

use strict;
use warnings;
no warnings qw/uninitialized/;

use File::Compare;
use File::Copy;

my $UPDATE    = 0;
my $REGEN     = 0;
my $SHARED    = 0;
my $MOBILE    = 0;
my $NO_UPLOAD = 0;
my $FLAGS     = '--missing-recent-report';
my $base_dir  = ".";
$base_dir = shift @ARGV if @ARGV;
$base_dir =~ s{/$}{};

my $scripts_dir  = "$base_dir/scripts";
my $filers_file  = "$base_dir/candidate_data/filers.json";
my $reports_path = "$base_dir/candidate_data/reports";
my $charts_path  = "$base_dir/charts/filers/reports";
my $reports_url  = "candidate-data/report-charts";
my $images_url   = (not $MOBILE) ? $reports_url : "images/candidate-data/reports";

$reports_path =~ s{/$}{};
$charts_path  =~ s{/$}{};

print STDERR "Checking for filers\n";
my @cpfids = `$scripts_dir/election/ocpf.py list-filers --reports $reports_path $FLAGS`;
chomp @cpfids;
@cpfids = grep $_, @cpfids;

my @charts;
my @images;
my @mobile_files;
my @tmps;
my $errors;
print STDERR "Found ${\(scalar @cpfids)} filer(s)\n";
foreach my $cpfid (@cpfids) {
    ## Get report
    my $tmp         = "/tmp/${cpfid}_reports.json";
    my $report_file = "$reports_path/${cpfid}_reports.json";
    my $chart_file  = "$charts_path/${cpfid}_report_chart.html";
    my $img_name    = "${cpfid}_report_chart.png";
    my $img_file    = "$charts_path/$img_name";
    my $mobile_file = "/tmp/${cpfid}_report_chart_mobile.html";
    my $updated;
    if (-f $report_file and -M $report_file < 1 and not $UPDATE) {
        print STDERR "Report file '$report_file' was written or checked today. Don't check for update\n";
    }
    else {
        print STDERR "Getting reports for filer $cpfid and saving them to $report_file\n";
        system "$scripts_dir/election/ocpf.py query-reports $cpfid $tmp 1>&2";
        if ($?) {
            print "Failed to query report for filer $cpfid: $?";
            $errors++;
        }
        elsif (-f $report_file and compare($tmp, $report_file) != 1) {
            print STDERR "No report update for filer $cpfid\n";
            system 'touch', $report_file;
        }
        else {
            ## Put report in place
            if (!move($tmp, $report_file)) {
                print "Failed to save file to '$report_file'\n";
                $errors++;
            }
            else {
                print "Report update for filer $cpfid saved in $report_file\n";
                $updated = 1;
            }
        }
    }

    $updated = ($updated || $REGEN);
    ## Make a chart from the report
    if (-f $report_file and (not -f $chart_file or $updated)) {
        print "Making chart and saving to '$chart_file'\n";
        system "$scripts_dir/election/plot_finances.py single-filer --out '$chart_file' --in-file '$report_file' --copyright-tight --h-legend 1>&2";
        if ($?) {
            $errors++;
            print "Failed to make chart file '$chart_file': $?\n";
        }
        else {
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
        print "Cannot make a chart file '$chart_file' as the report file '$report_file' is missing\n";
        $errors++;
    }

    ## Make an image file
    if (-f $report_file and (not -f $img_file or $updated)) {
        print "Making img and saving to '$img_file'\n";
        system "$scripts_dir/election/plot_finances.py single-filer --out '$img_file' --in-file '$report_file' --copyright-tight --h-legend --scale 2 1>&2";
        if ($?) {
            $errors++;
            print "Failed to make image file '$img_file': $?\n";
        }
        else {
            push @images, $img_file;
            if ($MOBILE) {
                if (write_mobile_file("/$images_url/$img_name", $mobile_file)) {
                    print "Wrote mobile file $mobile_file\n";
                    push @mobile_files, $mobile_file;
                    push @tmps, $mobile_file;
                }
            }
        }
    }
    elsif (not -f $img_file) {
        print "Making empty report image for filer $cpfid\n";
        system "convert -background white -fill black -pointsize 18 'label:No report data' $img_file";
        push @images, $img_file;
    }
    unlink $tmp if -f $tmp;
}

## Make shared charts
if (@charts or $SHARED) {
    ## Combined report
    my $chart_file = "$charts_path/combined_report_chart.html";
    print "Making combined report in '$chart_file'\n";
    system "$scripts_dir/election/plot_finances.py many-filers --out $chart_file --h-legend --copyright-tight $reports_path/*";
    if ($?) {
        $errors += 1;
        print "Couldn't make '$chart_file'\n";
    }
    else {
        push @charts, $chart_file;
    }

    ## Cash on hand report
    $chart_file = "$charts_path/cash_on_hand_report_chart.html";
    print "Making cash on hand report in '$chart_file'\n";
    system "$scripts_dir/election/plot_finances.py many-filers --coh --out $chart_file --h-legend --copyright-tight $reports_path/*";
    if ($?) {
        print "Couldn't make '$chart_file'\n";
        $errors += 1;
    }
    else {
        push @charts, $chart_file;
    }
}

## Finish up
system "$scripts_dir/add_no_cache.pl $_" foreach @charts;
my $total = @charts + @images + @mobile_files;
if ($total) {
    print "Made ${\(scalar @charts)} chart(s), ${\(scalar @images)} image(s), and ${\(scalar @mobile_files)} mobile file(s)\n";
}
else {
    print STDERR "No charts, images, or files made\n";
}

if ($NO_UPLOAD or not $total) {
    print STDERR "Skipping upload\n";
    unlink $_ foreach @tmps;
    exit ($errors) ? 1 : 0;
}

## Upload charts
my @files = (@charts, @mobile_files);
my $uploaded;
if (@files) {
    print "Moving ${\(scalar @files)} files to server\n";
    system '/bin/bash', '-c', "sftp -P19199 -i $ENV{HOME}/.ssh/charles_server_cx franklin\@franklin.cx:public_html/$reports_url <<< \$'put $_'" foreach @files;
    if ($?) {
        print STDERR "Failed to upload files to server: $?\n";
        $errors++;
    }
}

if (@images) {
    print "Moving ${\(scalar @images)} images to server\n";
    system '/bin/bash', '-c', "sftp -P19199 -i $ENV{HOME}/.ssh/charles_server_cx franklin\@franklin.cx:public_html/$images_url <<< \$'put $_'" foreach @images;
    if ($?) {
        print STDERR "Failed to upload charts to server: $?\n";
        $errors++;
    }
}

unlink $_ foreach @tmps;
exit ($errors) ? 1 : 0;

sub write_mobile_file {
    my $url = shift;
    my $file = shift;
    my $html = qq{
<html>
<head>
    <meta charset="utf-8" />
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
    <meta http-equiv="Pragma" content="no-cache" />
    <meta http-equiv="Expires" content="0" />
</head>
<body>
    <img src="$url"></img>
</body>
</html>
    };
    my $opened = open FILE, '>', $file;
    if (not $opened) {
        print STDERR "Failed to write to $file: $!";
        return 0;
    }
    print FILE $html;
    close FILE;
    return 1;
}
