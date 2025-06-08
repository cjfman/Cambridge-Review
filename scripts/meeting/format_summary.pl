#!/usr/bin/perl

use strict;
use warnings;
no warnings qw/uninitialized/;

use File::Basename;
use File::Spec::Functions 'catfile';
use Text::ParseWords;

my $print_files;
my $max_replacements = 1000;
my @agenda_dirs = (
    catfile(dirname(__FILE__), '../../meeting_data/processed'),
    catfile(dirname(__FILE__), '../../processed'),
);
my $glossary_url = '/the-city/city-glossary';
my $malegislature_url = 'https://malegislature.gov/Bills/194';
my $lines;
my %glossary = (
    AHO  => 'Affordable Housing Overlay',
    BZA  => 'Board of Zoning Appeals',
    CAMP => 'Cambridge Access and Mobility Plan',
    CDD  => 'Community Development Department',
    CHA  => 'Cambridge Housing Authority',
    CSD  => 'Community Safety Department',
    CSO  => 'Cycling Safety Ordinance',
    DPW  => 'Department of Public Works',
    PACE => 'Property Assessment Clean Energy Massachusetts',
    RFP  => 'Request for Proposal',
    STIR => 'Surveillance Technology Impact Report',
    STO  => 'Surveillance Technology Ordinance',
);

my %tooltip  = (
    ADA     => 'American Disabilities Act',
    CPD     => 'Cambridge Police Department',
    CPS     => 'Cambirdge Public Schools',
    DCR     => 'Department of Conservation and Recreation',
    EOPSS   => 'Executive Office of Public Safety',
    MassDEP => 'Massachusetts Department of Environmental Protection',
    MEMA    => 'Massachusetts Emergency Management Agency',
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
	## Breaks
	if (/^##(?!#)/) {
		print "\n<br><br>\n$_";
		next;
	}

    ## Replace keyword fields
    while (/\{\{([^\}]+)\}\}/) {
        last if $skip_replacements;
        if ($replacements >= $max_replacements) {
            print STDERR "Reached maximum number of replacements $max_replacements on line $line_no\n";
            $skip_replacements = 1;
            last;
        }
        my $found = $1;
        my $replacement;
        my ($name, $txt) = split /\|/, $found;
        $txt = $name unless defined $txt;
        $name =~ s/\s+/-/g;

        ## Determine replacement
        if ($name !~ /^[A-Z]+$/) {
            $name = lc $name;
        }
        if (defined $glossary{$name}) {
            ## Glossary term with tooltip
            print STDERR "Found glossary term with tooltip $name / $txt\n";
            $replacement = "[tooltips keyword='[$txt]($glossary_url#$name)' content='$glossary{$name}']";
        }
        elsif (defined $tooltip{$txt}) {
            ## Tooltip only
            print STDERR "Found tooltip $name / $tooltip{$name}\n";
            $replacement = "[tooltips keyword='$txt' content='$tooltip{$txt}']";
        }
        else {
            ## Glossary only
            print STDERR "Found glossary term $name / $txt\n";
            $replacement = "[$txt]($glossary_url#$name)";
        }

        ## Do replacement
        if (defined $replacement) {
            if (s/(\{\{[^\}]+\}\})/$replacement/) {
                print STDERR "Replacement '$found' >> '$replacement'\n";
                $replacements++;
            }
            else {
                print STDERR "Replacement failed\n";
            }
        }
        else {
            print STDERR "No replacement found\n";
        }
    }

    if ($skip_replacements) {
		print;
		next;
	}

    ## Insert agenda item links
    while (/(?<!\[|\>)\((\w+ \d+\s#\s?\d+)\)/) {
        my $uid = $1;
        $uid =~ s/(\w+ \d+)\s#\s?(\d+)/$1 #$2/;
        print STDERR "Found agenda item '$uid'\n";
        if (defined $item_links{$uid}) {
            my $replacement = make_link($uid, $item_links{$uid});
            if (s/$uid/$replacement/) {
                print STDERR "Replacement '$uid' >> $replacement\n";
                $replacements++;
            }
            else {
                print STDERR "Replacement failed\n";
                last;
            }
        }
        else {
            print STDERR "No details found for '$uid'\n";
            last;
        }
    }

    if ($skip_replacements) {
		print;
		next;
	}

    ## Insert MA legislature bill links
	while (/(?<!\[)\b([SH]D?[\. ]\d+)/) {
	#while (/(?<!\[)\b([SH]\.\d+)/) {
        my $uid = $1;
        print STDERR "Found MA legislature bill $uid\n";
        my $url = validate_bill_url($uid);
        if (defined $url) {
            my $replacement = "[$uid]($url)";
            if (s/\b\Q$uid\E\b/$replacement/) {
                print STDERR "Replacement $uid >> $replacement\n$_\n";
                $replacements++;
            }
            else {
                print STDERR "Replacement of $uid failed\n";
                last;
            }
        }
		else {
			print STDERR "Failed to validate $uid\n";
			last;
		}
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
    print STDERR "Opening '$path'\n" if $print_files;
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
        my $uid = $fields[$headers{'Unique Identifier'}];
        $uid =~ s/(\w+ \d+\s#)\s?(\d+)/$1$2/;
        $item_links{$uid} = $fields[$headers{Link}];
    }
    return %item_links;
}

sub validate_bill_url {
	return undef;
    my $bill = shift;
    $bill =~ s/[\. ]//g;
    my $url = "$malegislature_url/$bill";
    print STDERR "Validating $url\n";
    my $resp = `curl "$url" 2>/dev/null`;
    if ($resp =~ /404 - Page Not Found/i) {
        print STDERR "No such bill found\n";
        $url = undef;
    }
    return $url;
}

sub make_link {
	my ($text, $url) = @_;
	return qq{<a href="$url" target="_blank">$text</a>};
}
