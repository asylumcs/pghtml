#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
  pghtml.py
  MIT license (c) 2021 Asylum Computer Services LLC
  https://asylumcs.net
"""

# pylint: disable=C0103, R0912, R0915
# pylint: disable=too-many-instance-attributes, too-many-locals, no-self-use
# pylint: disable=bad-continuation, too-many-lines, too-many-public-methods

import sys
import os
import argparse
from time import strftime
import datetime
import regex as re  # for unicode support  (pip install regex)
from PIL import Image  # from pip install pillow
from html.parser import HTMLParser

showh = False
thetag = ""
theoutline = []


class MyHTMLParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        global showh, thetag
        if tag in "h1h2h3h4h5h6":
            thetag = tag + ": "
            showh = True

    def handle_data(self, data):
        global showh, thetag
        if showh:
            thetag = thetag + " " + data

    def handle_endtag(self, tag):
        global showh, thetag
        if tag in "h1h2h3h4h5h6":
            showh = False
            thetag = thetag.rstrip()
            thetag = re.sub(r"\s+", " ", thetag)
            m = re.match(r"h(\d)", thetag)
            if m:
                indent = "  " * int(m.group(1))
            theoutline.append("     " + indent + thetag)


parser = MyHTMLParser()


class Pghtml:
    """
    main class for pghtml
    """

    def __init__(self, args):
        """
        class initialization
        """
        self.t = []  # report
        self.wb = []  # working (wrapped) text
        self.wbuf = ""  # unwrapped text as string
        self.srcfile = args["infile"]
        self.outfile = args["outfile"]
        self.verbose = args["verbose"]
        self.root = os.path.dirname(os.path.realpath(__file__))
        self.sdir = ""  # to find the images
        self.encoding = ""
        self.NOW = strftime("%A, %Y-%m-%d %H:%M:%S")
        self.VERSION = "2021.07.24"
        self.onlyfiles = []  # list of files in images folder
        self.filedata = []  # string of image file information
        self.fsizes = []  # image tuple sorted by decreasing size
        self.links = {}
        self.targets = {}
        self.udefcss = {}  # user defined CSS
        self.usedcss = {}  # CSS used by user
        self.errormessage = ""  # for unwrap failure

    def crash(self):
        self.saveReport()
        exit(1)

    def fatal(self, message):
        """
        display (fatal) error and exit
        """
        sys.stderr.write("error: " + message + "\r\n")
        exit(1)

    def ap(self, s):
        """
        appends one line to report
        """
        self.t.append(s)

    def apl(self, thelist):
        """
        appends list of lines to report
        """
        for line in thelist:
            self.t.append(line)

    def loadFile(self):
        """
        load source file
        """
        empty = re.compile("^$")
        try:
            self.wbuf = open(self.srcfile, "r", encoding="UTF-8").read()
            self.encoding = "UTF-8"
            # remove BOM on first line if present
            t = ":".join("{0:x}".format(ord(c)) for c in self.wbuf[0])
            if t[0:4] == "feff":
                if len(self.wbuf[0]) > 1:
                    self.wbuf[0] = self.wbuf[0][1:]
                else:
                    self.wbuf = self.wbuf[1:]
        except UnicodeDecodeError:
            self.wbuf = open(self.srcfile, "r", encoding="Latin-1").read()
            self.encoding = "Latin-1"
        except:  # pylint: disable=bare-except
            self.fatal("loadFile: cannot open source file {}".format(self.srcfile))
        self.wb = self.wbuf.split("\n")
        self.wb = [s.rstrip() for s in self.wb]

        self.wb.append("")  # ensure file end
        while empty.match(self.wb[-1]):
            self.wb.pop()
        self.sdir = os.path.split(self.srcfile)[0]  # source directory (./images)
        if self.sdir == "":
            self.sdir = "."  # if we are running this in the same folder

    def limit(self, s, lnt):
        """
        process limit
        """
        if len(s) > lnt:
            s = s[:lnt] + "..."
        return s

    def miscChecks(self):
        """
        miscellaneous checks
        """
        self.ap("Miscellaneous checks")

        count = 0
        for line in self.wb:
            m = re.search("<table", line)
            if m:
                count += 1
        self.ap("  number of tables: {}".format(count))

        count = 0
        eflag = ""
        for line in self.wb:
            m = re.search("<h2", line)
            if m:
                count += 1
        if count == 0:
            eflag = "ERROR: "
        self.ap(
            "  {}number of h2 tags (usually chapters; should be > 0): {}".format(
                eflag, count
            )
        )

        count = 0
        for line in self.wb:
            m = re.search("<h3", line)
            if m:
                count += 1
        self.ap("  number of h3 tags (usually sections): {}".format(count))

        self.ap("  pixels used for sizing (images and borders only):")
        count = 0
        for line in self.wb:
            m = re.search(r"\d ?px", line)
            if m:
                self.ap("    {}".format(line))

        count = 0
        adh = []
        eflag = ""
        for line in self.wb:
            # ignore HTML comments (typically from ppgen)
            if "<!--" not in line and "-->" not in line and "--" in line:
                count += 1
                adh.append(line)
        if count != 0:
            eflag = "WARNING: "
        if count > 0:
            self.ap(
                '  {}lines with "--" instead of "???" (should be 0): {}'.format(
                    eflag, count
                )
            )
            for line in adh:
                self.ap("  {}".format(line))

    # -------------------------------------------------------------------------

    def scanImages(self):
        """
        image folder consistency
        filenames must be lower case and contain no spaces
        """
        r = []
        r.append("[pass] image folder consistency tests")
        for filename in self.onlyfiles:
            if " " in filename:
                r.append("  filename '{}' contains spaces".format(filename))
                r[0] = re.sub("pass", "???FAIL???", r[0])
            if re.search(r"\p{Lu}", filename):
                r.append("  filename '{}' not all lower case".format(filename))
                r[0] = re.sub("pass", "???FAIL???", r[0])

        # we have list of all files in self.onlyfiles
        # make sure all are images
        for filename in self.onlyfiles:
            try:
                with Image.open(self.sdir + "/images/" + filename) as im:
                    self.filedata.append(
                        "{}|{}|{}|{}".format(
                            filename, im.format, "%dx%d" % im.size, im.mode
                        )
                    )
            except IOError:
                r.append("  file '{}' is not an image".format(filename))
                r[0] = re.sub("pass", "???FAIL???", r[0])

        # information about all images are in self.filedata
        # verify image files are jpg (reported as JPEG) or png
        for fd in self.filedata:
            t = fd.split("|")
            if t[1] != "JPEG" and t[1] != "PNG":
                r.append("  file '{}' is of type {}".format(t[0], t[1]))
                r[0] = re.sub("pass", "???FAIL???", r[0])
        self.apl(r)

    def allImagesUsed(self):
        """
        verify all images in the HTML folder used in the HTML
        """
        r = []
        r.append("[pass] all images in the images folder used in the HTML")
        count_images = 0
        count_references = 0
        for fdata in self.filedata:
            t = fdata.split("|")[0]
            count_images += 1
            isUsed = False
            for line in self.wb:
                if t in line:
                    count_references += 1
                    isUsed = True
                    break
            if not isUsed:
                r.append("  image '{}' in images folder not used in HTML".format(t))
                r[0] = re.sub("pass", "???FAIL???", r[0])
        r[0] = r[0] + " ({} images)".format(count_images)
        self.apl(r)

    def allTargetsAvailable(self):
        """
        verify all target images in HTML available in images folder
        """
        r = []
        r.append("[pass] all target images in HTML available in images folder")

        for line in self.wb:
            m = re.search(r"[\p{L}-_\d]+\.(jpg|jpeg|png)", line)
            if m:
                filename = m[0]
                foundit = False
                for u in self.filedata:
                    fn = u.split("|")[0]
                    if fn == filename:
                        foundit = True
                        break
                if not foundit:
                    r.append(
                        "  image '{}' referenced in HTML not images folder".format(
                            filename
                        )
                    )
                    r[0] = re.sub("pass", "???FAIL???", r[0])
        self.apl(r)

    def allImages200k(self):
        """
        warn if any image larger than 200K
        show size of any > 100K
        """
        r = []
        r.append("[info] image file sizes")
        for fdata in self.filedata:
            fname = fdata.split("|")[0]
            fsize = os.path.getsize(self.sdir + "/images/{}".format(fname))
            self.fsizes.append([fname, fsize])
        self.fsizes.sort(key=lambda tup: tup[1], reverse=True)
        under256K = []
        above256K = []
        above1M = []
        for item in self.fsizes:
            if item[1] > 256 * 1024 and item[1] < 1024 * 1024:
                above256K.append(item)
            if item[1] <= 256 * 1024:
                under256K.append(item)
            if item[1] >= 1024 * 1024:
                above1M.append(item)
        if len(under256K) > 0:
            s = ""
            for t in under256K:
                s = "{} ({}K)".format(t[0], int(t[1] / 1024))
                r.append("  {}".format(s))
        if len(above256K) > 0:
            s = ""
            for t in above256K:
                s = "{} (???{}K???)".format(t[0], int(t[1] / 1024))
                r.append("  {}".format(s))
        if len(above1M) > 0:
            s = ""
            for t in above1M:
                s = "{} (???{}K???)".format(t[0], int(t[1] / 1024))
                r.append("  {}".format(s))
        self.apl(r)

    def imageSummary(self):
        """
        (if verbose), show all image data
        codes in fourth column:
            1 (1-bit pixels, black and white, stored with one pixel per byte)
            L (8-bit pixels, black and white)
            P (8-bit pixels, mapped to any other mode using a color palette)
            RGB (3x8-bit pixels, true color)
            RGBA (4x8-bit pixels, true color with transparency mask)
            CMYK (4x8-bit pixels, color separation)
            YCbCr (3x8-bit pixels, color video format)
            LAB (3x8-bit pixels, the L*a*b color space)
            HSV (3x8-bit pixels, Hue, Saturation, Value color space)
            I (32-bit signed integer pixels)
            F (32-bit floating point pixels)
        """
        ity = {}
        ity["1"] = "(1-bit pixels, black and white, stored with one pixel per byte)"
        ity["L"] = "(8-bit pixels, black and white)"
        ity["P"] = "(8-bit pixels, mapped to any other mode using a color palette)"
        ity["RGB"] = "(3x8-bit pixels, true color)"
        ity["RGBA"] = "(4x8-bit pixels, true color with transparency mask)"
        ity["CMYK"] = "(4x8-bit pixels, color separation)"
        ity["YCbCr"] = "(3x8-bit pixels, color video format)"
        ity["LAB"] = "(3x8-bit pixels, the L*a*b color space)"
        ity["HSV"] = "(3x8-bit pixels, Hue, Saturation, Value color space)"
        ity["I"] = "(32-bit signed integer pixels)"
        ity["F"] = "(32-bit floating point pixels)"

        r = []
        r.append("[info] image summary")
        for t in self.filedata:
            u = t.split("|")
            if u[3] in ity:
                mappedu3 = ity[u[3]]
            else:
                mappedu3 = u[3]
            r.append("    {}, {}, {} {}".format(u[0], u[2], u[1], mappedu3))
        self.apl(r)

    def coverImage(self):
        """
        cover image width must be >=650 px and height must be >= 1000 px
        """
        r = []
        r.append("[pass] cover image dimensions check")
        for t in self.filedata:
            u = t.split("|")
            if u[0] == "cover.jpg":
                width, height = u[2].split("x")
                if int(width) < 650 or int(height) < 1000:
                    r[0] = re.sub("pass", "???warn???", r[0])
                    r.append(
                        "       cover.jpg too small (actual: {}x{}, min: 650x1000)".format(
                            width, height
                        )
                    )
        self.apl(r)

    def otherImage(self):
        """
        if not the cover, then max dimension must be <= 5000x5000
        """
        r = []
        r.append("[pass] other image dimensions check")
        for t in self.filedata:
            u = t.split("|")
            if u[0] != "cover.jpg":
                width, height = u[2].split("x")
                if int(width) > 5000:
                    r[0] = re.sub("pass", "???warn???", r[0])
                    r.append(
                        "       {} dimension error (width {}px &gt; 5000px)".format(
                            u[0], width
                        )
                    )
                if int(height) > 5000:
                    r[0] = re.sub("pass", "???warn???", r[0])
                    r.append(
                        "       {} dimension error (height {}px &gt; 5000px)".format(
                            u[0], height
                        )
                    )
        self.apl(r)

    def imageTests(self):
        """
        consolidated image tests
        """
        self.ap("")
        t = "image tests"
        self.ap("----- {} ".format(t) + "-" * (73 - len(t)))

        # find filenames of all the images.
        mypath = self.sdir + "/images"
        if not os.path.isdir(mypath):
            self.ap("  *** no images folder found ***")
            return
        self.onlyfiles = [
            f for f in os.listdir(mypath) if os.path.isfile(os.path.join(mypath, f))
        ]

        self.scanImages()
        self.allImagesUsed()
        self.allTargetsAvailable()
        self.allImages200k()
        self.coverImage()
        self.otherImage()
        if self.verbose:
            self.imageSummary()

    # --------------------------------------------------------------------------------------

    def cleanExt(self):
        """
        report and remove external links of the form:
        href="https://www.gutenberg.org/files/55587/55587-h/55587-h.htm#Page_165"
        ignore boilerplate links similar to:
            "https://www.gutenberg.org", "https://www.gutenberg.org/donate"
        """
        r = []
        reported = False
        for i, line in enumerate(self.wb):
            m = re.search(r'<a href=([\'"]https?://.*?)>', line)
            m1 = re.search(r'[\'"]https?://www.gutenberg.org[\'"]>', line)
            m2 = re.search(r'[\'"]https?://www.gutenberg.org/donate/?[\'"]>', line)
            if m:
                if m1 or m2:  # ignore boilerplate links
                    continue
                if not reported:
                    r.append("[info] unexpected external links present")
                    reported = True
                r.append("  " + m.group(1))
                del self.wb[i]  # remove line containing external link
        if not reported:
            r.append("[pass] external links check")
        self.apl(r)

    def linkToCover(self):
        """
        either: provide a link in the document head, or
        put an id of coverpage on the img tag
        """
        r = []
        r.append("[pass] link to cover image for epub")
        coverlink = False
        i = 0
        while i < len(self.wb):
            if "coverpage" in self.wb[i]:
                coverlink = True
                break
            i += 1
        if not coverlink:
            r[0] = re.sub("pass", "???FAIL???", r[0])
        r2 = []
        for k, v in self.links.items():
            t = v.split(" ")  # look for multiple lines with same target
            if len(t) >= 2:
                if not reported:
                    r2.append("[???warn???] identical targets from multiple lines")
                    reported = True
                r2.append("  {} linked from lines {}".format(k, v))
        if len(r2) > 5:
            r.append(
                "[info] file appears to have an index. not reporting reused targets"
            )
        else:
            r = r + r2

        imagelink_count = 0
        oneiscover = ""
        for _, line in enumerate(self.wb):
            therefs = re.findall(r'href=["\']images/(.*?)["\']', line)
            for theref in therefs:
                if "cover." in theref:
                    oneiscover = theref
                imagelink_count += 1
        if imagelink_count > 0:
            if oneiscover:
                t001 = "links"
                if imagelink_count == 1:
                    t001 = "link"
                r.append(
                    "[info] file has {} {} to images (including {})".format(
                        imagelink_count, t001, oneiscover
                    )
                )
            else:
                r.append("[info] file has {} links to images".format(imagelink_count))
        self.apl(r)

    def findLinks(self):
        """
        internal links
           <a href="#CHAPTER_I">Phil and Serge</a>
         find links. create a hash table
         key=link target name
         value=line number the link occurs (or numbers)
        """
        r = []
        link_count = 0
        for i, line in enumerate(self.wb):
            therefs = re.findall(r'href=["\']#(.*?)["\']', line)
            for theref in therefs:
                link_count += 1
                tgt = theref
                # have a link. put it in links map
                if tgt in self.links:
                    self.links[tgt] = "{} {}".format(self.links[tgt], i)
                else:
                    self.links[tgt] = "{}".format(i)

        r.append(
            "[info] file has {} internal links to {} expected targets".format(
                link_count, len(self.links)
            )
        )
        self.apl(r)

    def findTargets(self):
        """
        find internal targets
        key=link target name
        value=line number where the target occurs (must be only one)
        """
        r = []
        reported = False
        id_count = 0
        for i, line in enumerate(self.wb):
            if "<meta" in line:
                continue
            theids = re.findall(r'id\s?=\s?["\'](.*?)["\']', line)
            for theid in theids:
                id_count += 1
                # have a link. put it in links map
                # format is self.targets["ch1"] = "214"
                # says the target "ch1" is on line "214"
                # if the target "ch1" is on multiple lines,
                # self.targets["ch1"] = "214 378"
                if theid in self.targets:
                    self.targets[theid] = "{} {}".format(self.targets[theid], i)
                else:
                    self.targets[theid] = "{}".format(i)

        # allow name='' as an alternate to id=''
        for i, line in enumerate(self.wb):
            if "<meta" in line:
                continue
            theids = re.findall(r'name\s?=\s?["\'](.*?)["\']', line)
            for theid in theids:
                if theid in self.targets:
                    # the id might already be in the map if it's there from an id=
                    # it's common: id='ch1" name='ch1'
                    # if it's a target on the same line, ignore it.
                    if str(i) not in self.targets[theid]:
                        self.targets[theid] = "{} {}".format(self.targets[theid], i)
                else:
                    self.targets[theid] = "{}".format(i)

        for k, v in self.targets.items():
            # if there is a space then we have multiple targets, which is an error
            t = v.split(" ")
            if len(t) > 1:
                if not reported:
                    r.append("[???FAIL???] duplicate targets")
                    reported = True
                r.append("  {} duplicate target on lines {}".format(k, v))
        r.append("[info] file has {} actual internal targets".format(len(self.targets)))
        self.apl(r)

    def doResolve(self):
        """
        every link must go to one link target that exists (or flag missing link target)
        every target should come from one or more links (or flag unused target)
        """
        r = []
        reported = False
        r.append("[pass] all links resolve to correct target")
        alllinks = list(self.links.keys())
        alltargets = list(self.targets.keys())
        for alink in alllinks:
            if alink not in alltargets:
                if not reported:
                    r[0] = re.sub("pass", "???FAIL???", r[0])
                    reported = True
                thelines = self.links[alink].split(" ")
                firstline = int(thelines[0]) + 1
                r.append(
                    "  target {} referenced from line {} not found".format(
                        alink, firstline
                    )
                )
        self.apl(r)

        r2 = []
        reported = 0
        report_limit = 20
        r2.append("[pass] all targets referenced by one or more href")
        alltargets = list(self.targets.keys())
        alllinks = list(self.links.keys())
        stmp = ""
        for atarget in alltargets:
            if atarget not in alllinks:
                if reported == 0:
                    r2[0] = "[info] targets not referenced with href"
                if reported == report_limit:
                    stmp = stmp[:-2] + " ... more not reported" + "  "
                    reported += 1
                    continue
                if reported > report_limit:
                    continue
                stmp += "{}, ".format(atarget)
                if len(stmp) > 60:
                    r2.append("  {}".format(stmp[:-2]))
                    stmp = ""
                reported += 1
        if stmp != "":  # the final line of the targets report
            r2.append("  {}".format(stmp[:-2]))
        self.apl(r2)

    def linkTests(self):
        """
        consolidated link tests
        """
        self.ap("")
        t = "link tests"
        self.ap("----- {} ".format(t) + "-" * (73 - len(t)))

        self.cleanExt()
        self.linkToCover()
        self.findLinks()
        self.findTargets()
        self.doResolve()

    # --------------------------------------------------------------------------------------

    def h1Title(self):
        """
        title check
        find what's in <title> and compare to what's in <h1>
        """
        r = []
        c_title = 0
        c_h1 = 0
        t1 = t2 = ""
        i = 0
        while i < len(self.wb):
            line = self.wb[i]

            m1 = re.search(r"<title>", line)
            if m1:
                s = ""
                while "</title>" not in self.wb[i]:
                    s += self.wb[i]
                    i += 1
                s += self.wb[i]
                m1 = re.search(r"<title>(.*?)<\/title>", s)
                if m1:
                    t1 = m1.group(1)
                t1 = re.sub("  +", " ", t1.strip())
                c_title += 1

            m1 = re.search(r"<h1", line)
            if m1:
                s = ""
                try:
                    while "</h1>" not in self.wb[i]:
                        s += self.wb[i]
                        i += 1
                except:
                    r.append("FATAL: no &lt;/h1> found")
                    self.apl(r)
                    self.crash()
                s += self.wb[i]
                m1 = re.search(r"<h1.*?>(.*?)<\/h1>", s)
                if m1:
                    t2 = m1.group(1)
                    t2 = re.sub("  +", " ", t2.strip())
                    c_h1 += 1
            i += 1

        badth1 = False
        if c_title == 0:
            r.append("[???FAIL???] missing &lt;title> directive")
            badth1 = True
        if c_h1 == 0:
            r.append("[???FAIL???] missing &lt;h1> element")
            badth1 = True
        if c_title > 1:
            r.append("[???FAIL???] too many &lt;title> directives")
            badth1 = True
        if c_h1 > 1:
            r.append("[???FAIL???] too many &lt;h1> elements")
            badth1 = True

        if not badth1:
            # clean up title
            t3 = t1.strip()

            # clean up h1
            t4 = re.sub(r"<br.*?>", "#", t2)
            t4 = re.sub(r"<.*?>", "", t4)
            t4 = re.sub(r"\s+", " ", t4)
            t4 = re.sub(r"#", " ", t4)
            r.append("[info] title/h1 compare:")
            r.append("       title: {}".format(t3))
            r.append("          h1: {}".format(t4))

            if "Gutenberg" not in t3:
                r.append("[???warn???] title should be of the form")
                r.append(
                    "         The Project Gutenberg eBook of Alice's Adventures in Wonderland,"
                    + " by Lewis Carroll"
                )
                # avoid trap in WWer's software (addhd.c)
                if "end" not in t3:
                    r.append("       or")
                    r.append(
                        "         Alice's Adventures in Wonderland, by Lewis Carroll&mdash;A"
                        + " Project Gutenberg eBook"
                    )
            if t3.endswith("."):
                r.append("  Information: title ends with full stop")
        self.apl(r)

    def spaceClose(self):
        """
        verify self-closing tags are of the form <XX />
        """
        r = []
        count = 0
        r.append("[pass] self-closing tag format")

        for line in self.wb:
            m = re.search(r"\S/>", line)
            if m:  # report only first five
                line = line.replace("<", "&lt;")
                if count == 0:
                    r[0] = "[???warn???] missing space before /&gt; closing tag"
                if count < 3:
                    r.append(" " * 9 + line.strip())
                if count == 5:
                    r.append(" " * 9 + "... more")
                count += 1
        self.apl(r)

    def langCheck(self):
        """
        show user what document claims is the language
        """
        r = []
        count = 0
        r.append("[user] please confirm the language code:")
        t = "  none specified"
        for line in self.wb:
            if re.search(r"<html.*?lang=", line):
                t = line.replace("<", "&lt;")
                break
        r.append("       {}".format(t))
        self.apl(r)

    def headingOutline(self):
        """
        show document
        """
        global theoutline
        theoutline.append("[info] document heading outline")
        self.wbuf2 = re.sub(r"&", "&amp;", self.wbuf)
        parser.feed(self.wbuf2)
        self.apl(theoutline)

    def preTags(self):
        """
        no pre tags in HTML
        """
        r = []
        r.append("[pass] no &lt;pre> tags")
        count = 0
        for line in self.wb:
            if "<pre" in line:
                count += 1
        if count != 0:
            r[0] = re.sub("pass", "???FAIL???", r[0])
            r.append("       number of &lt;pre> tags (should be 0): {}".format(count))
        self.apl(r)

    def charsetCheck(self):
        """
        character set should be UTF-8
        """
        r = []
        r.append("[info] charset check")
        cline = ""
        for line in self.wb:
            if "charset" in line:
                cline = line
        if cline == "":
            r[0] = re.sub("pass", "???FAIL???", r[0])
            r.append("       no charset found")
        else:
            r.append("       claimed: " + (cline.replace("<", "&lt;")).strip())
        info = os.popen("file {}".format(self.srcfile)).read()
        info = info.split(":")[1].strip()
        r.append("       detected: " + info.strip())
        self.apl(r)

    def DTDcheck(self):
        """
        check for valid document type
        update 2021.08.14 recognize HTML5 header
        """
        r = []
        r.append("[pass] Document Type Definition")
        cline = ""

        # check for HTML5
        if re.search("DOCTYPE html", self.wb[0], re.IGNORECASE):
            r.append("       Document appears to be HTML5")
            self.apl(r)
            return

        for i, line in enumerate(self.wb):
            if "DTD" in line:
                # find the DTD line and grab the next one
                # where we expect it to end
                cline = line
                cline2 = self.wb[i + 1]
                break
        if cline == "":
            r[0] = re.sub("pass", "???FAIL???", r[0])
            r.append("       no Document Type Definition found")
        else:
            # have the first line. if it's not a complete line, then
            # add the second with a '|'
            if not cline.endswith(">"):
                cline = cline + "|" + cline2
            # error if HTML version other than XHTML 1.0 Strict or 1.1
            # relies on the '|'
            if "XHTML 1.0 Strict" not in cline and "XHTML 1.1" not in cline:
                r[0] = re.sub("pass", "???warn???", r[0])
                r.append("       HTML version should be XHTML 1.0 Strict or 1.1")
                t001 = re.sub(r"\s+", " ", cline)
                t001 = re.sub(r"<", "&lt;", t001)
                if "|" in t001:
                    t002 = t001.split("|")
                    r.append("         {}".format(t002[0].strip()))
                    r.append("         {}".format(t002[1].strip()))
                else:
                    r.append("         {}".format(t001.strip()))

        self.apl(r)

    def altTags(self):
        """
        all img tags get evaluated for alt behavior
        """
        r = []
        r.append("[pass] image alt tag tests")
        alt_is_missing = 0
        alt_is_empty = 0
        alt_is_blank = 0
        alt_is_text = 0
        maxalttext = ""
        maxalttextlen = 0
        for i, line in enumerate(self.wb):
            if "<img" in line:
                j = i + 1
                while j < len(self.wb) and not line.endswith(">"):
                    line = line + " " + self.wb[j]
                    j += 1
                a01 = re.findall(r"alt=", line)
                if not a01:
                    alt_is_missing += 1
                a01 = re.findall(r"alt=['\"]['\"]", line)
                alt_is_empty += len(a01)
                a02 = re.findall(r"alt=['\"]\s+['\"]", line)
                alt_is_blank += len(a02)
                a03 = re.findall(r"alt=(['\"])([^\1]+)\1", line)
                alt_is_text += len(a03)
                for t in a03:
                    if len(t) > maxalttextlen:
                        maxalttextlen = len(t)
                        maxalttext = t
        if alt_is_missing > 0:
            r[0] = re.sub("pass", "???FAIL???", r[0])
            r.append("       some images have no alt tag")
        if alt_is_blank > 0:
            r[0] = re.sub("pass", "???FAIL???", r[0])
            r.append("       some images have non-empty blank alt tags")
        if maxalttextlen >= 10:
            r[0] = re.sub("pass", "???warn???", r[0])
            r.append("       alt text too long ({} chars)".format(maxalttextlen))
            r.append("         {}".format(maxalttext))

        r.append("       {} images with missing alt tags".format(alt_is_missing))
        r.append("       {} images with empty alt tags".format(alt_is_empty))
        r.append("       {} images with blank alt tags".format(alt_is_blank))
        r.append("       {} images with textual alt tags".format(alt_is_text))
        r.append("       max alt text length: {}".format(maxalttextlen))
        self.apl(r)

    def ppvTests(self):
        """
        consolidated tests particular to DP PPV
        """
        self.ap("")
        t = "DP tests"
        self.ap("----- {} ".format(t) + "-" * (73 - len(t)))

        self.h1Title()
        self.spaceClose()
        self.preTags()
        self.charsetCheck()
        self.DTDcheck()
        self.altTags()
        self.langCheck()
        self.headingOutline()

    # --------------------------------------------------------------------------------------

    def linelen(self):
        """
        line length for epub must be less than 2000
        """
        r = []
        r.append("[pass] line length check (9999 &lt; 2000)")
        maxlen = -1
        # maxline = -1
        for _, line in enumerate(self.wb):
            if len(line) > maxlen:
                maxlen = len(line)
                # maxline = i + 1
        if maxlen > 2000:
            r[0] = re.sub(r"pass", "???FAIL???", r[0])
            r[0] = re.sub(r"9999 &lt;", "{} >".format(maxlen), r[0])
        else:
            r[0] = re.sub(r"9999", "{}".format(maxlen), r[0])
        self.apl(r)

    def classchcount(self):
        """
        class chapter count and h2 count
        """
        r = []
        r.append("[info] class chapter count and h2 count")
        cchcount = 0
        h2count = 0
        for line in self.wb:
            n = re.findall(r"class=[\"']\bchapter\b[\"']", line)
            cchcount += len(n)
            n = re.findall(r"<h2", line)
            h2count += len(n)
        r.append("       {} class chapter, {} &lt;h2> tags".format(cchcount, h2count))
        self.apl(r)

    def pgTests(self):
        """
        consolidated tests particular to Project Gutenberg
        """
        self.ap("")
        t = "PG tests"
        self.ap("----- {} ".format(t) + "-" * (73 - len(t)))

        self.linelen()
        self.classchcount()

    # --------------------------------------------------------------------------------------

    def find_used_CSS(self):
        """
        CSS user has used in a class statement
        """
        for line in self.wb:
            m = re.findall(r"class=['\"](.*?)['\"]", line)
            if m:
                for mx in m:
                    mx2 = mx.split(" ")
                    for mx3 in mx2:
                        if mx3 != "":
                            self.usedcss[mx3] = 1

    def find_defined_CSS(self):
        """
        CSS user has defined is placed in udefcss map
        update: 2021/08/14 HTML5 CSS block recognized
        """
        t = []  # place to build a CSS block
        i = 0

        while i < len(self.wb):
            style4 = bool(re.search(r"style.*?type.*?text.*?css", self.wb[i]))
            style5 = bool(re.search(r"<style>", self.wb[i]))
            if style4 or style5:
                break
            i += 1
        if i == len(self.wb):
            exit("no CSS definition found")
        i += 1  # move into the CSS

        while i < len(self.wb) and "</style>" not in self.wb[i]:
            t.append(self.wb[i])  # append everything until the closing </style>
            i += 1

        # there may be a user's second CSS block (as used by DPC)
        # continue and look for another

        while i < len(self.wb) and not bool(
            re.search(r"style.*?type.*?text.*?css", self.wb[i])
        ):
            i += 1  # advance; if no 2nd CSS will go to end
        i += 1

        while i < len(self.wb) and "</style>" not in self.wb[i]:
            t.append(self.wb[i])
            i += 1

        # strip out any comments in css
        i = 0
        while i < len(t):
            if t[i].strip().startswith("/*") and t[i].strip().endswith("*/"):
                del t[i]
                continue
            if t[i].strip().startswith("/*"):
                del t[i]
                while not t[i].strip().endswith("*/"):
                    del t[i]
                del t[i]
            i += 1

        # unwrap CSS
        i = 0
        while i < len(t):
            while i < len(t) - 1 and t[i].count("{") != t[i].count("}"):
                t[i] = t[i] + " " + t[i + 1]
                del t[i + 1]
            if t[i].count("{") != t[i].count("}"):
                s = re.sub(r"\s+", " ", t[i])
                s = s.strip()
                if len(s) > 40:
                    s = s[0:40] + "..."
                self.fatal("runaway CSS block near: {}".format(s))
            t[i] = re.sub(r"\s+", " ", t[i])
            t[i] = t[i].strip()
            i += 1

        # remove @media bracketing
        for i, _ in enumerate(t):
            t[i] = t[i].strip()
            if "@media" in t[i]:
                t[i] = re.sub(r"@media.*?{", "", t[i])
                t[i] = re.sub(r"}$", "", t[i])
            t[i] = t[i].strip()

        # remove definitions
        # ".large { font-size: large; }" -> ".large"
        for i, _ in enumerate(t):
            t[i] = re.sub(r"{[^}]+}", "", t[i])
            t[i] = t[i].strip()

        # remove
        # div.linegroup > :first-child
        for i, _ in enumerate(t):
            t[i] = re.sub(r">.*", "", t[i])
            t[i] = t[i].strip()

        # remove
        # "hr.pb" -> ".pb"
        # div.poem.apdx -> ".poem.apdx" which will become ".poem .apdx" below
        for i, _ in enumerate(t):
            t[i] = re.sub(r"\p{L}+(\.\p{L}+)", r"\1", t[i])

        for s in t:
            s = s.replace(".", " .")  # ".poem.apdx" becomes " .poem .apdx"
            s = s.replace("  ", " ")
            s = s.strip()
            s = s.replace(",", " ")  # splits h1,h2,h3 {}
            utmp = s.split(" ")  # splits .linegroup .group
            for u00 in utmp:
                # classes that are not pseudo-classes
                if u00.startswith(".") and ":" not in u00:
                    self.udefcss[u00[1:]] = 1

    def resolve_CSS(self):
        """
        resolve CSS used and defined
        usedcss and udefcss
        """

        r = []
        r.append("[info] CSS checks")

        # show all CSS
        r.append("  defined CSS:")
        s = ""
        for key in sorted(self.udefcss):
            s = s + " " + key
            if len(s) > 60:
                r.append("    " + s.strip())
                s = ""
        if s != "":
            r.append("   " + s)

        r.append("  used CSS:")
        s = ""
        for key in sorted(self.usedcss):
            s = s + " " + key
            if len(s) > 60:
                r.append("    " + s.strip())
                s = ""
        if s != "":
            r.append("   " + s)

        # CSS used in a class but not defined
        css_used_not_defined = False
        badk = {}
        for key in self.usedcss:
            if key not in self.udefcss:
                badk[key] = 1
        if badk:
            css_used_not_defined = True
            s = ""
            r.append("  not defined but used:")
            for k in sorted(badk):
                s = s + " " + k
                if len(s) > 60:
                    r.append("    " + s.strip())
                    s = ""
            if s != "":
                r.append("   " + s)

        # CSS defined but not used in a class
        css_defined_not_used = False
        badk = []
        for key in self.udefcss:
            if key not in self.usedcss:
                badk.append(key)
        if badk:
            css_defined_not_used = True
            s = ""
            r.append("  defined but not used:")
            for k in sorted(badk):
                s = s + " " + k
                if len(s) > 60:
                    r.append("    " + s.strip())
                    s = ""
            if s != "":
                r.append("   " + s)

        # adjust the message

        if css_used_not_defined or css_defined_not_used:
            r[0] = re.sub(r"info", "???warn???", r[0])
        s = ""
        if css_used_not_defined and css_defined_not_used:
            r[0] = r[0] + " (unused CSS, undefined CSS)"
        else:
            if css_used_not_defined:
                r[0] = r[0] + " (not defined but used)"
            if css_defined_not_used:
                r[0] = r[0] + " (defined but not used)"
        self.apl(r)

    def testCSS(self):
        """
        CSS tests
        """
        self.ap("")
        t = "CSS tests"
        self.ap("----- {} ".format(t) + "-" * (73 - len(t)))

        self.find_used_CSS()
        self.find_defined_CSS()
        self.resolve_CSS()

    # --------------------------------------------------------------------------------------

    def saveReport(self):
        """
        save report with same encoding as source file
        """
        # see if we have a qualified name or not
        base = os.path.basename(self.outfile)
        # if they're equal, user gave us an unqualified name (just a file name,
        # no path to it)
        if base == self.outfile:
            # construct path into source directory
            fn = os.path.join(
                os.path.dirname(os.path.realpath(self.srcfile)), self.outfile
            )
        else:
            fn = self.outfile

        f1 = open(fn, "w", encoding="{}".format(self.encoding))

        # if self.encoding == "UTF-8":
        #    f1.write("\ufeff")  # BOM if UTF-8

        hdr = [
            "<html>",
            "<head>",
            '<meta charset="utf-8">',
            '<meta name=viewport content="width=device-width, initial-scale=1">',
            "<title>pghtml report</title>",
            '<style type="text/css">',
            "body { margin-left: 1em;}",
            ".red { color:red; }",
            ".green { color:green; }",
            ".redonyel { color:red; background-color: #FFFFAA; }",
            ".greenonyel { color:green; background-color: #FFFFAA; }",
            ".silverfade { color:silver; }",
            ".black { color:black; }",
            ".dim { color:#999999; }",
            ".warn { color:brown; background-color:white; }",
            "td { padding-right:2em; }",
            "table { margin-left:2em; }",
            "</style>",
            "</head>",
            "<body>",
            "<pre>",
        ]

        for line in hdr:
            f1.write(line + "\n")

        f1.write("pghtml run report\n")
        f1.write(f"run started: {str(datetime.datetime.now())}\n")
        f1.write("source file: {}\n".format(os.path.basename(self.srcfile)))
        f1.write(
            f"<span style='background-color:#FFFFDD'>close this window to return to the UWB.</span>\n"
        )

        # output test results
        for s in self.t:

            # there should not be any HTML tags in the report
            # if they are, put them in silver
            # s = s.replace("<", "<span class='silverfade'>&lt;")
            # s = s.replace(">", "&gt;</span>")

            s = s.replace("???", "<span class='red'>")
            s = s.replace("???", "<span class='green'>")
            s = s.replace("???", "<span class='redonyel'>")
            s = s.replace("???", "<span class='greenonyel'>")
            s = s.replace("???", "<span class='dim'>")
            s = s.replace("???", "<span class='black'>")
            s = s.replace("???", "<span class='warn'>")
            s = s.replace("???", "</span>")
            s = s.replace("???", "<")
            s = s.replace("???", ">")

            f1.write("{:s}\r\n".format(s))

        # footer
        f1.write("-" * 80 + "\r\n")
        f1.write("run complete")
        ftr = ["</pre>", "</body>", "</html>"]
        for line in ftr:
            f1.write(line)

        f1.close()

    def run(self):
        """
        run function sequence
        """

        self.loadFile()
        self.imageTests()
        self.linkTests()
        self.ppvTests()
        self.pgTests()
        self.testCSS()
        self.saveReport()

    def __str__(self):
        return "pghtml"


def parse_args():
    """
    parse user-supplied arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--infile", help="input file", required=True)
    parser.add_argument("-o", "--outfile", help="output file", required=True)
    parser.add_argument("-v", "--verbose", help="verbose", action="store_true")
    args = vars(parser.parse_args())
    return args


def main():
    """
    main entry point
    """
    args = parse_args()
    pghtml = Pghtml(args)
    pghtml.run()


if __name__ == "__main__":
    sys.exit(main())
