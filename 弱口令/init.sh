#!/bin/bash
# ============================================================
# MySQL 容器首次启动时自动执行本脚本，完成建库建表与数据投放
# 想换 flag / 账号 / 金额，直接改本文件后重新初始化数据库即可：
#   docker compose down -v && docker compose up -d --build
# ============================================================
set -e

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" --default-character-set=utf8mb4 <<'EOSQL'

CREATE DATABASE IF NOT EXISTS `user_system`
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `user_system`;

-- ---------------------------- 管理员账号 ----------------------------
-- 只有 admin 能登录，密码 666666（MD5 存储）
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id`       INT AUTO_INCREMENT PRIMARY KEY,
  `username` VARCHAR(50) NOT NULL,
  `password` VARCHAR(32) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO `users` (`username`, `password`) VALUES
  ('admin', MD5('666666'));

-- ---------------------------- 业务用户 ----------------------------
-- 用户二的 notice 字段即“第二段 flag”（库里存明文，后端返回时做 Base64 编码）
-- Pr1ce_Tamp3r1ng!} 的 Base64 = UHIxY2VfVGFtcDNyMW5nIX0=，进入用户二订单页时弹窗
DROP TABLE IF EXISTS `customers`;
CREATE TABLE `customers` (
  `id`     INT AUTO_INCREMENT PRIMARY KEY,
  `name`   VARCHAR(50)  NOT NULL,
  `notice` VARCHAR(255) NOT NULL DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO `customers` (`id`, `name`, `notice`) VALUES
  (1, '汪桑', ''),
  (2, 'hacker', 'Pr1ce_Tamp3r1ng!}');

-- ---------------------------- 订单信息 ----------------------------
-- 用户一未付款金额 1000，是 BP 改包考点
DROP TABLE IF EXISTS `orders`;
CREATE TABLE `orders` (
  `id`          INT AUTO_INCREMENT PRIMARY KEY,
  `customer_id` INT NOT NULL,
  `order_no`    VARCHAR(50),
  `product`     VARCHAR(100),
  `amount`      DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `status`      VARCHAR(20)  NOT NULL DEFAULT '未付款'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO `orders` (`customer_id`, `order_no`, `product`, `amount`, `status`) VALUES
  (1, 'ORD20260901001', '玉足',     1000.00, '未付款'),
  (2, 'ORD20260901002', '打开就送', 0.01,    '未付款');

-- ---------------------------- 第一段 flag ----------------------------
-- 库里存明文，后端返回时做 Base64 编码
-- flag{Cl1ent_S1de_ 的 Base64 = ZmxhZ3tDbDFlbnRfUzFkZV8=
-- 抓包把应付款金额改成小于 10，付款成功后由后端读出并弹窗
DROP TABLE IF EXISTS `secrets`;
CREATE TABLE `secrets` (
  `id`    INT AUTO_INCREMENT PRIMARY KEY,
  `name`  VARCHAR(64)  NOT NULL,
  `value` VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO `secrets` (`name`, `value`) VALUES
  ('pay_flag', 'flag{Cl1ent_S1de_');

-- 最终完整 flag = 两段 Base64 分别解码后再拼接：
--   base64_decode(ZmxhZ3tDbDFlbnRfUzFkZV8=) = flag{Cl1ent_S1de_
--   base64_decode(UHIxY2VfVGFtcDNyMW5nIX0=) = Pr1ce_Tamp3r1ng!}
--   拼接 => flag{Cl1ent_S1de_Pr1ce_Tamp3r1ng!}

-- ---------------------------- Web 连接账号 ----------------------------
CREATE USER IF NOT EXISTS 'ctf'@'%' IDENTIFIED BY 'ctf123456';
GRANT ALL PRIVILEGES ON `user_system`.* TO 'ctf'@'%';
FLUSH PRIVILEGES;

EOSQL

echo "[init.sh] user_system 数据库初始化完成"
