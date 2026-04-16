package io.sparge.server;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class SpargeConstantsTest {

    @Test
    void knownTrackingDomainIsPixel() {
        assertTrue(SpargeConstants.isTrackingPixel(
                "https://stats.wordpress.com/g.gif", "", ""));
    }

    @Test
    void googleAnalyticsIsPixel() {
        assertTrue(SpargeConstants.isTrackingPixel(
                "https://www.google-analytics.com/collect", "", ""));
    }

    @Test
    void oneByone1pxIsPixelByDimension() {
        assertTrue(SpargeConstants.isTrackingPixel(
                "https://example.com/img.gif", "1", "1"));
    }

    @Test
    void zeroByzeroIsPixelByDimension() {
        assertTrue(SpargeConstants.isTrackingPixel(
                "https://example.com/img.gif", "0", "0"));
    }

    @Test
    void normalImageIsNotPixel() {
        assertFalse(SpargeConstants.isTrackingPixel(
                "https://example.com/photo.jpg", "800", "600"));
    }

    @Test
    void localImageIsNotPixel() {
        assertFalse(SpargeConstants.isTrackingPixel(
                "../../assets/photo.jpg", "", ""));
    }

    @Test
    void unknownDomainWithLargeDimensionsIsNotPixel() {
        assertFalse(SpargeConstants.isTrackingPixel(
                "https://cdn.example.com/img.png", "100", "100"));
    }

    @Test
    void dimensionCheckRequiresHttpSrc() {
        assertFalse(SpargeConstants.isTrackingPixel(
                "../../assets/spacer.gif", "1", "1"));
    }

    @Test
    void trackingDomainsNotEmpty() {
        assertFalse(SpargeConstants.TRACKING_DOMAINS.isEmpty());
        assertTrue(SpargeConstants.TRACKING_DOMAINS.contains("stats.wordpress.com"));
    }

    @Test
    void chromeSelectorsNotEmpty() {
        assertFalse(SpargeConstants.CHROME_SELECTORS.isEmpty());
    }

    @Test
    void missingImgSignalsNotEmpty() {
        assertFalse(SpargeConstants.MISSING_IMG_SIGNALS.isEmpty());
    }

    @Test
    void codeSignalsStrongNotEmpty() {
        assertFalse(SpargeConstants.CODE_SIGNALS_STRONG.isEmpty());
    }
}
