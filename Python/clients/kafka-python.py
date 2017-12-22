import sys

from kafka import KafkaProducer, KafkaConsumer

DEFUALT_KAFKA_HOST = 'IP:9092'
KAFKA_TOPIC = ''
MESSAGE = b'Test message'

def produce(KAFKA_HOST, MESSAGE):
    producer = KafkaProducer(bootstrap_servers=KAFKA_HOST)
    producer.send(KAFKA_TOPIC, MESSAGE)


def consume(KAFKA_HOST):
    consumer = KafkaConsumer(KAFKA_TOPIC, bootstrap_servers=KAFKA_HOST, 
                            auto_offset_reset='earliest')
    
    try:
        for message in consumer:
            print(message.value)
    except KeyboardInterrupt:
        sys.exit()

if __name__ == '__main__':
        KAFKA_HOST = sys.argv[1]
        arg = sys.argv[2]
    except IndexError:
        print "Missing args"
        sys.exit()

    if arg == 'pull':
        consume(KAFKA_HOST)
    else:
        produce(KAFKA_HOST, MESSAGE)
        sys.exit()
