# Production Deployment Guide - Selenium Optimizations

## Quick Deployment Steps

### 1. Pull Latest Changes
```bash
# SSH to your production server
ssh root@mail.tamermap.com

# Navigate to app directory
cd /home/tamermap/app

# Pull latest changes
git pull origin main
```

### 2. Restart Monitor Service
```bash
# Restart the monitor (it will use the new optimized code)
sudo systemctl restart tamermap

# Check status
sudo systemctl status tamermap

# View logs to verify optimization
tail -f /home/tamermap/app/logs/monitor.log
```

### 3. Verify Optimization (Optional)
```bash
# Check if monitor is running with new code
ps aux | grep monitor.py

# Monitor resource usage during next Selenium test
htop  # Watch CPU/memory during test
```

## Expected Results

### Immediate Improvements
- **CPU spikes**: Should reduce from 100% to 20-40% during Selenium tests
- **Memory usage**: Should reduce significantly during tests
- **Test duration**: Should complete 50% faster

### Monitoring
- Watch the monitor logs for "Testing Stripe.js loading (optimized)" messages
- Monitor system resources during the next test cycle (every 30 minutes)
- Check for any error messages in the logs

## Configuration Options

### Adjust Test Frequency (Optional)
If you want to run Selenium tests less frequently:

```bash
# Edit the systemd service file
sudo nano /etc/systemd/system/tamermap.service

# Add this environment variable to the ExecStartPost line:
Environment="SELENIUM_TEST_INTERVAL=3600"  # Run every hour instead of 30 minutes

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart tamermap
```

### Recommended Settings
- **Current**: 30 minutes (good for critical systems)
- **Conservative**: 1 hour (3600 seconds)
- **Low traffic**: 2 hours (7200 seconds)

## Troubleshooting

### If Monitor Fails to Start
```bash
# Check logs
sudo journalctl -u tamermap -f

# Check Python dependencies
cd /home/tamermap/app
source venv/bin/activate
python3 -c "import selenium; print('Selenium OK')"
```

### If Selenium Tests Fail
```bash
# Check Chrome/ChromeDriver
which google-chrome
which chromedriver

# Update ChromeDriver if needed
cd /home/tamermap/app
source venv/bin/activate
python3 -c "from webdriver_manager.chrome import ChromeDriverManager; print(ChromeDriverManager().install())"
```

### Performance Monitoring
```bash
# Monitor system resources
htop
iotop
nethogs

# Check specific process usage
ps aux | grep -E "(monitor|chrome)" | head -10
```

## Rollback Plan

If issues arise, you can quickly rollback:

```bash
# Revert to previous commit
git reset --hard HEAD~1

# Restart service
sudo systemctl restart tamermap
```

## Success Metrics

After deployment, you should see:
1. **Lower CPU spikes** during monitoring cycles
2. **Faster test execution** (15s vs 30s+)
3. **Reduced memory pressure** during tests
4. **Same test coverage** maintained
5. **Cleaner monitor logs** with optimization messages

## Next Steps

1. **Deploy and monitor** for 24-48 hours
2. **Adjust test frequency** if resources allow
3. **Consider additional optimizations** if needed
4. **Monitor overall system performance** improvement

## Support

For deployment issues:
1. Check monitor logs first
2. Verify git pull was successful
3. Check systemd service status
4. Monitor system resources during tests
