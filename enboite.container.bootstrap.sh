# docker run -it --name ssh --rm -p 2057:22 debian:13

apt-get update && apt-get install -y openssh-server openssl

printf 'root:%s\n' "$bootstrap_password_root" | chpasswd

mkdir -p /run/sshd
chmod 0755 /run/sshd

cat /etc/ssh/sshd_config

echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config
echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config

/usr/sbin/sshd