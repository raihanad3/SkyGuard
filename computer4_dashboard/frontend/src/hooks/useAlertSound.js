import { useEffect, useRef } from 'react';

const SOUND_MAP = {
  HIGH: '/saya_akan_lawan.mp3',
  MEDIUM: '/no_no_no_jotaro.mp3',
  LOW: '/yes_yes_yes_jotaro.mp3',
};

const THRESHOLDS = {
  HIGH: 1,
  MEDIUM: 20,
  LOW: 50,
};

export function useAlertSound(apiBaseUrl = 'http://localhost:8000') {
  const lastAlertIdRef = useRef(0);
  const audioRef = useRef(null);
  const lastPlayedLevelRef = useRef(null); // Track which sound was played last

  useEffect(() => {
    // Initialize audio immediately (don't wait for click)
    audioRef.current = new Audio();
    console.log('🔊 Audio initialized');

    // Enable autoplay on first click
    const enableAutoplay = () => {
      console.log('✅ User interaction detected - autoplay enabled');
    };
    document.addEventListener('click', enableAutoplay, { once: true });

    // Poll alerts every 10 seconds
    const pollAlerts = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/alerts/recent?since_id=${lastAlertIdRef.current}&limit=500`);
        if (!response.ok) return;

        const alerts = await response.json();
        if (!alerts || alerts.length === 0) return;

        // Count by level
        const counts = { HIGH: 0, MEDIUM: 0, LOW: 0 };
        alerts.forEach((alert) => {
          if (counts[alert.alert_level] !== undefined) {
            counts[alert.alert_level]++;
          }
        });

        console.log('📊 Alert counts:', counts);

        // Apply boost/penalty to balance competition
        const MEDIUM_BOOST = 2;
        const LOW_PENALTY = 0.5;  // Divide by 2
        const weighted = {
          HIGH: counts.HIGH,
          MEDIUM: counts.MEDIUM * MEDIUM_BOOST,
          LOW: counts.LOW * LOW_PENALTY
        };

        console.log('⚖️ Weighted counts:', weighted);

        // Play sound based on which level has the MOST (after weighting)
        let soundFile = null;
        const maxCount = Math.max(weighted.HIGH, weighted.MEDIUM, weighted.LOW);
        
        if (maxCount === 0) {
          console.log('⚠️ No alerts (silent)');
        } else if (counts.HIGH === maxCount) {
          soundFile = SOUND_MAP.HIGH;
          console.log(`✅ HIGH has most alerts (${counts.HIGH}) → Playing:`, soundFile);
        } else if (counts.MEDIUM === maxCount) {
          soundFile = SOUND_MAP.MEDIUM;
          console.log(`✅ MEDIUM has most alerts (${counts.MEDIUM}) → Playing:`, soundFile);
        } else if (counts.LOW === maxCount) {
          soundFile = SOUND_MAP.LOW;
          console.log(`✅ LOW has most alerts (${counts.LOW}) → Playing:`, soundFile);
        }

        // Play sound
        if (soundFile) {
          if (!audioRef.current) {
            console.error('❌ Audio not initialized!');
            return;
          }
          
          console.log('🔊 Attempting to play:', soundFile);
          audioRef.current.src = soundFile;
          audioRef.current.play()
            .then(() => console.log('✅ Successfully played:', soundFile))
            .catch((err) => console.error('❌ Audio blocked:', err.message));
        }

        // Update last seen ID
        const maxId = Math.max(...alerts.map((a) => a.id));
        lastAlertIdRef.current = maxId;
      } catch (error) {
        console.error('❌ Alert polling error:', error);
      }
    };

    const interval = setInterval(pollAlerts, 10000);
    pollAlerts(); // Initial poll

    return () => clearInterval(interval);
  }, [apiBaseUrl]);

  return null;
}
