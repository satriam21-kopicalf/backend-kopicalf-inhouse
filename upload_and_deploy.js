const { Client } = require('ssh2');
const fs = require('fs');

const conn = new Client();
conn.on('ready', () => {
    console.log('SSH Connected!');
    
    // Upload the tarball
    conn.sftp((err, sftp) => {
        if (err) { console.error('SFTP Error:', err); conn.end(); return; }
        console.log('Uploading files...');
        sftp.fastPut('/tmp/be_changes.tar.gz', '/tmp/be_changes.tar.gz', (err) => {
            if (err) { console.error('Upload Error:', err); conn.end(); return; }
            console.log('Upload complete!');
            
            // Extract and deploy
            const commands = [
                'cd /root/be-kopicalf-inhouse && tar -xzf /tmp/be_changes.tar.gz',
                'cd /root/be-kopicalf-inhouse && docker compose restart api celery_worker',
                'cd /root/be-kopicalf-inhouse && docker compose ps',
                'cd /root/be-kopicalf-inhouse && docker compose logs --tail=20 api'
            ];
            
            let idx = 0;
            function runNext() {
                if (idx >= commands.length) {
                    conn.end();
                    console.log('\n✓ Deployment complete!');
                    return;
                }
                console.log('\n> ' + commands[idx]);
                conn.exec(commands[idx], (err, stream) => {
                    if (err) { console.error('Error:', err); conn.end(); return; }
                    stream.on('data', (data) => process.stdout.write(data.toString()));
                    stream.stderr.on('data', (data) => process.stderr.write(data.toString()));
                    stream.on('close', () => { idx++; runNext(); });
                });
            }
            runNext();
        });
    });
});

conn.on('error', (err) => console.error('SSH Error:', err.message));

conn.connect({
    host: '187.52.114.14',
    port: 22,
    username: 'root',
    password: 'Kopicalf2019#',
    readyTimeout: 30000
});
