package etl.core;

public class EtlException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    public EtlException(String message, Throwable cause) {
        super(message, cause);
    }

    public EtlException(String message) {
        super(message);
    }
}
